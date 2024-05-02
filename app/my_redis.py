import asyncio
import random
import string
from time import time as unix
import app.encoders as encoders
import app.decoders as decoders

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
    
    async def handle_commands(self, raw, commands, client_reader, client_writer,replica=False):
        while len(commands)!=0:
            replica_replconf = replica and commands[0].upper()=="REPLCONF"
            responses,commands = self.handle_command(commands[0],commands[1:],(client_reader,client_writer)) #pass command and args
            if not isinstance(responses, list):
                responses = [responses]
            if not replica or replica_replconf:
                for response in responses:
                    client_writer.write(response.encode("utf-8"))
                    await client_writer.drain()
    
    async def handle_client(self,client_reader,client_writer,replica=False):
        while True:
            data = await client_reader.read(1024)
            if not data:
                break
            decoded_data = data.decode()
            rest = decoders.BaseDecoder.preprocess(decoded_data)
            commands = []
            while len(rest)!=0:
                cmd,rest = decoders.BaseDecoder.decode(rest)
                commands+=cmd
            await self.handle_commands(data, commands, client_reader,client_writer,replica)
            self.offset+=len(data)
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
            
    async def send_handshake_data(self, sock, reads, *args):
        reader, writer = sock
        sends = encoders.Array([encoders.BulkString(x) for x in args])
        writer.write(sends.encode("utf-8"))
        await writer.drain()
        return await reader.read(reads)#.decode()
        
    async def copy_rdb(self, reader):
        #fucking race conditions
        r= await reader.read(1) # $
        last = b''
        count = 0
        while True:
            read = await reader.read(1)
            try:
                num = int(read)
                count*=10
                count+=num
            except ValueError:
                last=read
                break
        rdb = last + await reader.read(count+1)# +1 for \n from \r\n; of which \r already read above

    async def handshake(self, sock):
        reader, _ = sock
        print(await self.send_handshake_data(sock,7, "PING"))
        print(await self.send_handshake_data(sock,5, "REPLCONF","listening-port",str(self.port)))
        print(await self.send_handshake_data(sock,5, "REPLCONF","capa","psync2"))
        print(await self.send_handshake_data(sock,56, "PSYNC","?","-1"))
        #rdb = await sock[0].read(1024)
        #print(rdb)
        await self.copy_rdb(reader)

    async def start_slave(self):
        sock = await asyncio.open_connection(*self.replicaof)
        await self.handshake(sock)
        return asyncio.create_task(self.handle_client(*sock,True))

class ReplicatableRedisMaster(BaseRedisMaster):
    def __init__(self, host, port):
        super().__init__(host,port)
        self.propagates: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = []

    def command_psync(self, args):
        return [encoders.SimpleString(f"FULLRESYNC {self.replicationId} {self.offset}"),
                self.generate_rdb()
            ], args[2:]

    async def handle_commands(self, raw, commands, client_reader, client_writer,replica=False):
        while len(commands)!=0:
            #override add propagate
            if commands[0].upper() in ("SET","DEL"):
                await self.propagate(raw)
            replica_replconf = replica and commands[0].upper()=="REPLCONF"
            responses,commands = self.handle_command(commands[0],commands[1:],(client_reader,client_writer)) #pass command and args
            if not isinstance(responses, list):
                responses = [responses]
            if not replica or replica_replconf:
                for response in responses:
                    client_writer.write(response.encode("utf-8"))
                    await client_writer.drain()

    def handle_command(self,command,args,asyncsock):
        try:
            command_method = getattr(self, f"command_{command.lower()}")
            print(command_method)
            #override add propagate sockets
            if command.upper() == "REPLCONF" and args[0]=="listening-port":
                self.propagates.append(asyncsock)
            return command_method(args)
        except AttributeError:
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
    
    def command_ping(self,args):
        return encoders.SimpleString("PONG"), args #takes no args

    def command_echo(self,args):
        return encoders.BulkString(args[0]),args[1:]

    def command_replconf(self, args):
        if self.role=="master":
            return encoders.SimpleString("OK"), args[2:]
        else:
            return encoders.Array([encoders.BulkString(x) for x in ["REPLCONF","ACK",str(self.data)]]), args[2:]

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
            args = args[2:]
        return write, getresp, time, args
    
    def command_set(self,args):
        restargs = args[2:]
        write, response, time, restargs = self.set_command_args(args[0],restargs)
        if write:
            self.state[args[0]] = args[1],time
        return response,restargs
    
    def command_get(self, args):
        value,time = self.state.get(args[0],(None,-1))
        if time!=-1 and time<unix():
            value = None
            del self.state[args[0]]
        if value is None:
            return encoders.NullBulkString(), args[1:]
        return encoders.BulkString(value),args[1:]

    def replication_section(self):
        info = {"role":self.role, "master_replid":self.replicationId, "master_repl_offset":self.offset}
        
        return encoders.BulkString(info)

    def command_info(self, args):
        if args[0] == "replication":
            response = self.replication_section()
            args = args[1:]
        return response, args

    async def start(self):
        coros =[self.start_master()]
        if self.role=="slave":
            coros.append(self.start_slave())
        await asyncio.gather(*coros)