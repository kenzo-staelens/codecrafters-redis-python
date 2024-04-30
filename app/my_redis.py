import asyncio
import socket
import app.encoders as encoders
import app.decoders as decoders

class BaseRedisServer:
    def __init__(self, sock: socket.socket):
        self.socket = sock
    
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

    def event_handler(self,sock):
        while True:
            command = sock.recv(1024).decode()
            commands,_ = decoders.BaseDecoder.decode(decoders.BaseDecoder.preprocess(command))
            print(command,commands)
            for command in commands:
                response = self.handle_command(command)
                sock.send(response.encode("utf-8"))

    def start(self):
        while True:
            sock,addr = self.socket.accept()
            asyncio.create_task(self.event_handler(sock))

class RedisServer(BaseRedisServer):
    def command_ping(self, command):
        return encoders.SimpleString("PONG")