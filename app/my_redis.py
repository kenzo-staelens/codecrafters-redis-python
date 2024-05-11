import asyncio
import random
import string
from time import time as unix
import app.encoders as encoders
import app.decoders as decoders
from app.argtypes import asyncioSock
import traceback

def generate_id(length):
    return ''.join(random.choices(string.ascii_lowercase+string.digits, k = length))

class BaseRedis:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.state: dict[str,tuple[str,float]] = {}
        self.offset = 0

    def generate_rdb(self):
        empty_rdb = "524544495330303131fa0972656469732d76657205372e322e30fa0a72656469732d62697473c040fa056374696d65c26d08bc65fa08757365642d6d656dc2b0c41000fa08616f662d62617365c000fff06e3bfec0ff5aa2"
        empty_rdb = bytes.fromhex(empty_rdb)
        return encoders.RDBFile(empty_rdb)
    
    def no_command_handler(self,command):
        print(f"command not found {command}")
        return encoders.SimpleError(f"command {command} not found")

    def handle_command(self,command,args,asyncsock):
        try:
            command_method = getattr(self, f"command_{command.lower()}")
            return command_method(args)
        except AttributeError:
            return self.no_command_handler(command)
    
    async def shadow_handle_commands(self, command, client_reader, client_writer, replica=False):
        command,_ = command
        replica_replconf = replica and command[0].upper()=="REPLCONF"
        responses = self.handle_command(command[0],command[1:],(client_reader,client_writer))
        if not isinstance(responses, list):
            responses = [responses]
        if not replica or replica_replconf:
            for response in responses:
                client_writer.write(response.encode("utf-8"))
                await client_writer.drain()

    async def handle_client(self,client_reader,client_writer,decoder=None):
        replica = False
        if decoder is not None:
            replica = True
        else:
            decoder = decoders.StreamDecoder()
        while True:
            while decoder.size()!=0:
                try:
                    command=decoder.get()
                    await self.shadow_handle_commands(command, client_reader,client_writer,replica)
                    if replica:
                        self.offset+=len(command[1])
                except Exception as e:
                    print(traceback.format_exc())
            data = await client_reader.read(1024)
            if not data:
                break
            decoder.write(data)
        client_writer.close()

class BaseRedisMaster(BaseRedis):
    def __init__(self, host,port):
        super().__init__(host,port)
        self.role = "master"
        self.replicaof = None
        self.replicationId = generate_id(40)
    
    async def start_master(self):
        server = await asyncio.start_server(self.handle_client, host=self.host,port=self.port)
        async with server:
            await server.serve_forever()

class BaseRedisSlave(BaseRedis):
    def __init__(self,host, port, replicaof=None):
        super().__init__(host,port)
        if replicaof:
            self.role="slave"
            self.replicaof = replicaof
            
    async def send_handshake_data(self, sock, decoder: decoders.StreamDecoder, *args):
        reader, writer = sock
        sends = encoders.Array([encoders.BulkString(x) for x in args])
        writer.write(sends.encode("utf-8"))
        await writer.drain()
        read = await reader.read(1024)
        decoder.write(read)
        
    async def copy_rdb(self, rdb):
        pass

    async def handshake(self, sock: asyncioSock, decoder: decoders.StreamDecoder):
        await self.send_handshake_data(sock,decoder, "PING")
        await self.send_handshake_data(sock,decoder, "REPLCONF","listening-port",str(self.port))
        await self.send_handshake_data(sock,decoder, "REPLCONF","capa","psync2")
        await self.send_handshake_data(sock,decoder, "PSYNC","?","-1")
        decoder.getmany(4) # pong, ok, ok, fullsync
        await asyncio.sleep(1)#wait for rdb to arrive
        try:
            rdb = decoder.get(False) #no decode
            await self.copy_rdb(rdb)
        except Exception as e:
            print(e)

    async def start_slave(self):
        sock: asyncioSock = await asyncio.open_connection(*self.replicaof)
        decoder = decoders.StreamDecoder()
        await self.handshake(sock,decoder)
        return asyncio.create_task(self.handle_client(*sock,decoder))

class ReplicatableRedisMaster(BaseRedisMaster):
    def __init__(self, host, port):
        super().__init__(host,port)
        self.propagates: list[asyncioSock] = []

    def command_psync(self, _):
        return [encoders.SimpleString(f"FULLRESYNC {self.replicationId} {self.offset}"),
                self.generate_rdb()
            ]

    async def fn_propagate(self,command):
        command, raw = command
        if command[0].upper() in ("SET","DEL"):
            await self.propagate(raw)

    async def shadow_handle_commands(self, command, client_reader, client_writer, replica=False):
        await self.fn_propagate(command)
        return await super().shadow_handle_commands(command, client_reader, client_writer, replica)

    def handle_command(self,command,args,asyncsock):
        try:
            command_method = getattr(self, f"command_{command.lower()}")
            #override add propagate sockets
            if command.lower() == "replconf" and args[0]=="listening-port":
                self.propagates.append(asyncsock)
            return command_method(args)
        except AttributeError as e:
            return self.no_command_handler(command)
    
    async def propagate(self, data):
        for _,writer in self.propagates:
            try:
                writer.write(data)
                await writer.drain()
            except IOError as e:
                print(e)
        self.propagates = [(reader,writer) for reader,writer in self.propagates if not writer.is_closing()]

class RedisServer(ReplicatableRedisMaster, BaseRedisSlave):
    def __init__(self, host, port, replicaof=None):
        ReplicatableRedisMaster.__init__(self,host,port)
        BaseRedisSlave.__init__(self,host,port,replicaof)
    
    def command_ping(self,_):
        return encoders.SimpleString("PONG")

    def command_echo(self,args):
        return encoders.BulkString(args[0])
    
    def command_replconf(self, _):
        if self.role=="master":
            return encoders.SimpleString("OK")
        else:
            return encoders.Array([encoders.BulkString(x) for x in ["REPLCONF","ACK",str(self.offset)]])

    def set_command_args(self,key, args):
        write,getresp, time = True, encoders.SimpleString("OK"), -1
        if len(args)>0 and args[0].upper() in ("NX","XX"):
            if args[0]=="NX" and key in self.state or \
                args[0]=="XX" and key not in self.state:
                write = False
            args = args[1:]
        if len(args)>0 and args[0].upper() == "GET":
            pass #return the string or error
            self.command_get([key])
            args = args[1:]
        if len(args)>0 and args[0].upper() == "KEEPTTL":
            args = args[1:] # do nothing
        elif len(args)>0 and args[0].upper() in ("EX","PX","EXAT","PXAT"):
            if not args[1].startswith("E"):
                args[1]=float(args[1])/1000
            time = float(args[1]) + (unix() if not args[0].endswith("AT") else 0)
        return write, getresp, time
    
    def command_set(self,args):
        args = args[2:] #set value
        write, response, time = self.set_command_args(args[0],args)
        if write:
            self.state[args[0]] = args[1],time
        return response
    
    def command_get(self, args):
        value,time = self.state.get(args[0],(None,-1))
        if time!=-1 and time<unix():
            value = None
            del self.state[args[0]]
        if value is None:
            return encoders.NullBulkString()
        return encoders.BulkString(value)

    def command_wait(self,args):
        print(args)
        return encoders.Integer(0)

    def replication_section(self):
        info = {"role":self.role, "master_replid":self.replicationId, "master_repl_offset":self.offset}
        return encoders.BulkString(info)

    def command_info(self, args):
        if args[0] == "replication":
            response = self.replication_section()
        return response

    async def start(self):
        coros = [self.start_master()]
        if self.role=="slave":
            coros.append(self.start_slave())
        await asyncio.gather(*coros)