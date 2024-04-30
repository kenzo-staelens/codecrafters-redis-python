import socket
from app.my_redis import RedisServer

def main():
    server_socket = socket.create_server(("localhost", 6379), reuse_port=True)
    server_socket.listen()
    redis = RedisServer(server_socket)
    redis.start()


if __name__ == "__main__":
    main()
