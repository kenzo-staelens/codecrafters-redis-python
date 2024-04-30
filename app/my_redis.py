import asyncio
from time import time as unix
import app.encoders as encoders
import app.decoders as decoders

class BaseRedisServer:
    def __init__(self, host,port):
        self.host = host
        self.port = port
        self.state: dict[str,tuple[str,float]] = {}
    
    def no_command_handler(self,command):
        print(f"command not found {command}")
        pass #pass for now

    def handle_command(self,command,args):
        try:
            command_method = getattr(self, f"command_{command.lower()}")
            return command_method(args)
        except AttributeError:
            self.no_command_handler(command)
            return ""

    async def handle_client(self,client_reader,client_writer):
        while True:
            data = await client_reader.read(1024)
            if not data:
                break
            data = data.decode()
            commands,_ = decoders.BaseDecoder.decode(decoders.BaseDecoder.preprocess(data))
            while len(commands)!=0:
                response,commands = self.handle_command(commands[0],commands[1:]) #pass command and args
                client_writer.write(response.encode("utf-8"))
                await client_writer.drain()
        client_writer.close()
    
    async def start(self):
        server = await asyncio.start_server(self.handle_client, host=self.host,port=self.port)
        await server.serve_forever()
    
class RedisServer(BaseRedisServer):
    def command_ping(self,args):
        return encoders.SimpleString("PONG"), args #takes no args

    def command_echo(self,args):
        return encoders.BulkString(args[0]),args[1:]

    def set_command_args(self,key, args):
        write = True
        getresp = None
        time = -1
        if len(args)>0 and args[0].upper() in ("NX","XX"):
            if args[0]=="NX" and key in self.state or \
                args[0]=="XX" and key not in self.state:
                write = False
            args = args[1:]
        if len(args)>0 and args[0].upper() == "GET":
            pass #return the string or error
            getresp = self.state.get(key)
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
        write, getresp, time, restargs = self.set_command_args(args[0],restargs)
        if write:
            self.state[args[0]] = args[1],time
        return encoders.SimpleString("OK"),restargs
    
    def command_get(self, args):
        value,time = self.state.get(args[0],(None,-1))
        if time!=-1 and time<unix():
            value = None
            del self.state[args[0]]
        if value is None:
            return encoders.NullBulkString(), args[1:]
        return encoders.BulkString(value),args[1:]