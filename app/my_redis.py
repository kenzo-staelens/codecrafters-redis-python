import asyncio
import app.encoders as encoders
import app.decoders as decoders

class BaseRedisServer:
    def __init__(self, host,port):
        self.host = host
        self.port = port
        self.state = {}
    
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

    def command_set(self,args):
        self.state[args[0]] = args[1]
        return encoders.SimpleString("OK"),args[2:]
    
    def command_get(self, args):
        value = self.state.get(args[0])
        if value is None:
            return encoders.Null(), args[1:]
        return encoders.BulkString(value),args[1:]