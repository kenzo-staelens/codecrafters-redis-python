import asyncio
import random
import socket
import string
from time import time as unix
import app.encoders as encoders
import app.decoders as decoders

def generate_id(length):
    return ''.join(random.choices(string.ascii_lowercase+string.digits, k = length))

class BaseRedisMaster:
    def __init__(self, host,port):
        self.host = host
        self.port = port
        self.state: dict[str,tuple[str,float]] = {}
        self.role = "master"
        self.replicaof = None
        self.replicationId = generate_id(40)
        self.offset = 0
    
    def generate_rdb(self):
        empty_rdb = "524544495330303131fa0972656469732d76657205372e322e30fa0a72656469732d62697473c040fa056374696d65c26d08bc65fa08757365642d6d656dc2b0c41000fa08616f662d62617365c000fff06e3bfec0ff5aa2"
        empty_rdb = bytes.fromhex(empty_rdb)
        return encoders.RDBFile(empty_rdb)

    def no_command_handler(self,command):
        print(f"command not found {command}")
        return encoders.SimpleError(f"command {command} not found"),args

    def propagate(self,data):
        pass #notimplementederror will cause issues

    def handle_command(self,command,args,asyncsock):
        try:
            command_method = getattr(self, f"command_{command.lower()}")
            return command_method(args)
        except AttributeError:
            return self.no_command_handler(command)

    async def handle_commands(self, raw, commands, client_reader, client_writer):
        while len(commands)!=0:
            responses,commands = self.handle_command(commands[0],commands[1:],(client_reader,client_writer)) #pass command and args
            if not isinstance(responses, list):
                responses = [responses]
            for response in responses:
                client_writer.write(response.encode("utf-8"))
                await client_writer.drain()

    async def handle_client(self,client_reader,client_writer):
        while not client_reader.at_eof():
            data = await client_reader.read(1024)
            if self.role=="slave":
                print(data)
            if not data:
                break
            decoded_data = data.decode()
            commands,_ = decoders.BaseDecoder.decode(decoders.BaseDecoder.preprocess(decoded_data))
            await self.handle_commands(data, commands, client_reader,client_writer)
        client_writer.close()
    
    async def start_master(self):
        server = await asyncio.start_server(self.handle_client, host=self.host,port=self.port)
        await server.serve_forever()

class BaseRedisSlave:
    def __init__(self,host, port, replicaof=None):
        self.host = host
        self.port = port
        if replicaof:
            self.role="slave"
            self.replicaof = replicaof
            self.replica_socket = self.handshake()
    
    def send_handshake_data(self, sock, *args):
        sends = encoders.Array([encoders.BulkString(x) for x in args])
        sock.sendall(sends.encode("utf-8"))
        resp = sock.recv(1024).decode()
        return

    def copy_rdb(self, rdb):
        pass

    def handshake(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self.host,self.port))
        sock.connect(self.replicaof)
        self.send_handshake_data(sock, "PING")
        self.send_handshake_data(sock, "REPLCONF","listening-port",str(self.port))
        self.send_handshake_data(sock, "REPLCONF","capa","psync2")
        self.send_handshake_data(sock, "PSYNC","?","-1")
        rdb = sock.recv(1024)
        self.copy_rdb(rdb)
        return sock

    async def start_slave(self):
        server = await asyncio.start_server(self.handle_client, sock = self.replica_socket,backlog=1)
        await server.serve_forever()

class ReplicatableRedisMaster(BaseRedisMaster):
    def __init__(self, host, port):
        super().__init__(host,port)
        self.propagates: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = []
    
    def command_replconf(self, args):
        return encoders.SimpleString("OK"), args[2:]

    def command_psync(self, args):
        return [encoders.SimpleString(f"FULLRESYNC {self.replicationId} {self.offset}"),
                self.generate_rdb()
            ], args[2:]

    async def handle_commands(self, raw, commands, client_reader, client_writer):
        while len(commands)!=0:
            if commands[0].upper() in ("SET","DEL"):
                await self.propagate(raw)
            responses,commands = self.handle_command(commands[0],commands[1:],(client_reader,client_writer)) #pass command and args
            if not isinstance(responses, list):
                responses = [responses]
            for response in responses:
                client_writer.write(response.encode("utf-8"))
                await client_writer.drain()

    def handle_command(self,command,args,asyncsock):
        try:
            command_method = getattr(self, f"command_{command.lower()}")
            if command.lower() == "replconf" and args[0]=="listening-port":
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
        print(len(self.propagates))

class RedisServer(ReplicatableRedisMaster, BaseRedisSlave):
    def __init__(self, host, port, replicaof=None):
        ReplicatableRedisMaster.__init__(self,host,port)
        BaseRedisSlave.__init__(self,host,port,replicaof)
    
    def command_ping(self,args):
        return encoders.SimpleString("PONG"), args #takes no args

    def command_echo(self,args):
        return encoders.BulkString(args[0]),args[1:]

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
        if self.role=="master":
            await self.start_master()
        else:
            await self.start_slave()