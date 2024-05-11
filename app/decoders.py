from abc import abstractmethod
from queue import Queue
import queue
from typing import Any, Generator, List, Tuple

TERMINATOR = b"\r\n"
REDIS = [82, 69, 68, 73, 83] # REDIS


class StringStream:
    def __init__(self, str: bytes=b"") -> None:
        self.stream: Queue = Queue()
        self.__iadd__(str)
    
    def __iadd__(self, str: bytes=b""):
        for item in str:
            self.stream.put(item)
        return self

    def peek(self) -> str:
        if self.stream.qsize()==0:
            return None
        return self.stream.queue[0]

    def read(self) -> str:
        return self.stream.get()

    def readmany(self, count: int ) -> str:
        return [self.stream.get() for _ in range(count)]
    
    def has_next(self) -> bool:
        return self.stream.qsize()>0

    def assertTerminator(self):
        readterm = self.readmany(len(TERMINATOR))
        if readterm!=[x for x in TERMINATOR]: #converts to array
            raise ValueError(f"unexpected value {readterm}, expected {TERMINATOR}")

    def size(self):
        return self.stream.qsize()


class StreamDecoder():
    def __init__(self) -> None:
        self.data: Queue = Queue()
        self.stream: StringStream = StringStream()
    
    def write(self, data: bytes) -> None:
        self.stream += data
        #while stringstream.has_next():
        #    decoded = BaseDecoder.decode(stringstream)
        #    self.data.put(decoded)

    def get(self,decode=True) -> Any:
        # lazy decode
        decoded,raw = BaseDecoder.decode(self.stream)
        if decode:
            decoded = self.decode_command(decoded)
        self.data.put((decoded,raw))

        return self.data.get()
    
    def getmany(self,count=1,decode=True) -> List[Any]:
        return [self.get(decode) for _ in range(count)] 

    def size(self):
        return self.stream.size()
    
    def decode_command(self, command):
        if isinstance(command[0],int):
            return "".join(chr(x) for x in command)
        return ["".join(chr(x) for x in c) for c in command]

class BaseDecoder:
    @classmethod
    def decode(cls, stringstream):
        token = stringstream.read().to_bytes(1,"little")
        decoder = decoder_table[token]
        decoded,raw = decoder._decode(stringstream)
        return decoded, token+raw

    @classmethod
    @abstractmethod
    def _decode(cls,stringstream):
        pass

    @classmethod
    def read_number(cls,stringstream:StringStream)-> int:
        raw = b""
        num = 0
        while stringstream.peek() in range(48,58): #numeric
            read = stringstream.read()
            num*=10
            num+=read-48 #"0"
            raw+=read.to_bytes(1,"little")
        return num, raw

class SimpleStringDecoder(BaseDecoder):
    @classmethod
    def _decode(cls,stringstream: StringStream):
        raw = b""
        decoded = []
        while stringstream.peek()!=ord("\r"):
            read = stringstream.read()
            decoded.append(read)
            raw+=read.to_bytes(1,"little")
        stringstream.assertTerminator()
        return decoded, raw+TERMINATOR

class ArrayDecoder(BaseDecoder):
    @classmethod
    def _decode(cls,stringstream):
        length,raw = cls.read_number(stringstream)
        stringstream.assertTerminator()
        raw+=TERMINATOR
        decoded = []
        for _ in range(length):
            decoded_item,dec_raw = cls.decode(stringstream)
            decoded.append(decoded_item)
            raw+=dec_raw
        return decoded,raw

class BulkStringDecoder(BaseDecoder):
    @classmethod
    def _decode(cls,stringstream: StringStream):
        length,raw = cls.read_number(stringstream)
        stringstream.assertTerminator()
        decoded = stringstream.readmany(length)
        raw+=TERMINATOR+bytes(decoded)
        if not decoded[:5]==REDIS: #rdb file
            stringstream.assertTerminator()
            raw+=TERMINATOR
        return decoded, raw

decoder_table = {
    b"*": ArrayDecoder,
    b"$": BulkStringDecoder,
    b"+": SimpleStringDecoder
}