import asyncio
import socket
import app.encoders as encoders
import app.decoders as decoders

class BaseRedisServer:
    def __init__(self, host,port):
        self.host = host
        self.port = port
    
    def no_command_handler(self,command):
        print(f"command not found {command}")
        pass #pass for now

    def handle_command(self,command):
        try:
            command_method = getattr(self, f"command_{command.lower()}")
            return command_method(command)
        except AttributeError:
            self.no_command_handler(command)
            return ""

    async def handle_client(self,client_reader,client_writer):
        while True:
            command = await client_reader.read(1024)
            if not command:
                break
            command = command.decode()
            commands,_ = decoders.BaseDecoder.decode(decoders.BaseDecoder.preprocess(command))
            for command in commands:
                response = self.handle_command(command)
                client_writer.write(response.encode("utf-8"))
                await client_writer.drain()
        client_writer.close()
    
    async def start(self):
        server = await asyncio.start_server(self.handle_client, host=self.host,port=self.port)
        await server.serve_forever()
    
class RedisServer(BaseRedisServer):
    def command_ping(self, command):
        return encoders.SimpleString("PONG")