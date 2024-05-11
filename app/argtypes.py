from argparse import Action,ArgumentError
import asyncio
from typing import Tuple, List

asyncioSock = Tuple[asyncio.StreamReader, asyncio.StreamWriter]
replicaConn = Tuple[asyncioSock, int]

class StringInteger(Action):
    """Action for argparse that allows argument, a string and integer, 
    with different types.
    This factory function returns an Action subclass that is
    configured with the integer default.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        message = ''
        if len(values)!=2:
            message = f'argument "{self.dest}" requires 2 arguments'
        try:
            values[1] = int(values[1])
        except ValueError:
            message = f'second argument to "{self.dest}" requires an integer'
        if message:
            raise ArgumentError(self, message)
        setattr(namespace, self.dest, tuple(values))