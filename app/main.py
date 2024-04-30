import asyncio
from app.my_redis import RedisServer

async def main():
    #server_socket = socket.create_server(("localhost", 6379), reuse_port=True)
    #server_socket.listen()
    
    redis = RedisServer("localhost",6379)
    await redis.start()


if __name__ == "__main__":
    asyncio.run(main())
