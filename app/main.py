from argparse import ArgumentParser
import asyncio
import sys
from app.my_redis import RedisServer
from app.argtypes import StringInteger

async def main(args):
    redis = RedisServer("localhost",args.port, replicaof=args.replicaof)
    await redis.start()

if __name__ == "__main__":
    parser = ArgumentParser(prog="Redis",description="python redis implementation")
    parser.add_argument("--port",type=int, default=6379)
    parser.add_argument("--replicaof",nargs=2, action=StringInteger, metavar=("MASTER_HOST","MASTER_PORT"))
    args = parser.parse_args(sys.argv[1:])

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nexiting")
        sys.exit()