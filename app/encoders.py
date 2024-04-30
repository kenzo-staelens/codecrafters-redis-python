TERMINATOR = "\r\n"

class RESP:
    def encode(self, format):
        return self.encoded.encode(format)

    def __str__(self) -> str:
        return self.encoded

    def __repr__(self) -> str:
        return self.encoded

class SimpleRESP(RESP):
    def __init__(self, token, value):
        self.token = token
        self.value = value
    
    @property
    def encoded(self):
        return f"{self.token}{self.value}{TERMINATOR}"
    
    @encoded.setter
    def encoded(self,_):
        pass

class AggregateRESP(RESP):
    def __init__(self, token, values):
        self.token = token
        self.values = values

    @property
    def encoded(self):
        converted_values = [str(v) for v in self.values]
        return f"{self.token}{TERMINATOR.join(converted_values)}{TERMINATOR}"

    @encoded.setter
    def encoded(self,_):
        pass

class SimpleString(SimpleRESP):
    def __init__(self, value):
        super().__init__("+",value)
    
class SimpleError(SimpleRESP):
    def __init__(self, value):
        super().__init__("-",value)

class Integer(SimpleRESP):
    def __init__(self, value):
        super().__init__(":",value)

class Null(SimpleRESP):
    def __init__(self, _=""):
        super().__init__("_","")

class Boolean(SimpleRESP):
    def __init__(self, value):
        super().__init__("#",value)

class Double(SimpleRESP):
    def __init__(self, value):
        super().__init__(",",value)

class BigNumber(SimpleRESP):
    def __init__(self, value):
        super().__init__("(",value)

class BulkString(AggregateRESP):
    def __init__(self, value):
        super().__init__("$",(len(value),value))

class NullBulkString(SimpleRESP):
    def __init__(self, _=""):
        super().__init__("$","-1")