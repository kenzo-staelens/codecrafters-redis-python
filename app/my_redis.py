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
            command_method = getattr(self, f"command_{command}")
            return command_method(command)
        except AttributeError:
            self.no_command_handler(command)

    def start(self):
        sock,addr = self.socket.accept()
        command = sock.recv(1024).decode()
        commands,_ = decoders.BaseDecoder.decode(decoders.BaseDecoder.preprocess(command))
        for command in commands:
            response = self.handle_command(command)
            sock.send(response.encode("utf-8"))

class RedisServer(BaseRedisServer):
    def command_ping(self, command):
        return encoders.SimpleString("PONG")