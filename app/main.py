from argparse import ArgumentParser
import asyncio
import sys
from app.my_redis import RedisServer

async def main(args):
    #server_socket = socket.create_server(("localhost", 6379), reuse_port=True)
    #server_socket.listen()
    redis = RedisServer("localhost",args.port)
    await redis.start()
    

if __name__ == "__main__":
    parser = ArgumentParser(prog="Redis",description="python redis implementation")
    parser.add_argument("--port",type=int, default=6379)
    args = parser.parse_args()
    print(args)
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nexiting")
        sys.exit()