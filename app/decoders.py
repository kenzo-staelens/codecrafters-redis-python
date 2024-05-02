from abc import abstractmethod

TERMINATOR = "\r\n"

class BaseDecoder:
    @classmethod
    def preprocess(cls,value):
        split = value.split(TERMINATOR)
        if split[-1]=="":
            return split[:-1]
        return split

    @classmethod
    @abstractmethod
    def _decode(cls,value):
        pass
        
    @classmethod
    def decode(cls,value):
        token = value[0][0]
        decoder = decoder_table[token]
        value[0] = value[0][1:] #remove indicator
        return decoder._decode(value)

class ArrayDecoder(BaseDecoder):
    @classmethod
    def _decode(cls,value):
        length = int(value[0])
        value = value[1:] #remove array indicator
        decoded = []
        for _ in range(length):
            decoded_item, value = cls.decode(value)
            decoded.append(decoded_item)
        return decoded, value

class BulkStringDecoder(BaseDecoder):
    @classmethod
    def _decode(cls,value):
        length = int(value[0])
        #assume decoded string is of correct size
        decoded = value[1]
        if len(decoded)!=length:
            raise ValueError("BulkString not of correct length")
        return decoded, value[2:]

decoder_table = {
    "*": ArrayDecoder,
    "$": BulkStringDecoder
}