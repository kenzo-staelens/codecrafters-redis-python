import socket
import app.encoders as encoders

class BaseRedisServer:
    def __init__(self, sock: socket.socket):
        self.socket = sock
    
    def no_command_handler(self,command):
        pass #pass for now

    def handle_command(self,command):
        try:
            method = getattr(self, f"command_{command}")
            method(command)
        except AttributeError:
            self.no_command_handler(self,command)

    def start(self):
        command = self.socket.recv(1024).decode()
        response = self.handle_command(command)
        self.socket.send(response.encode("utf-8"))

class RedisServer(BaseRedisServer):
    def command_ping(self, command):
        return encoders.SimpleString("PONG")