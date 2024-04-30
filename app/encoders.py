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
        self.skip_terminator=False

    @property
    def encoded(self):
        converted_values = [str(v) for v in self.values]
        represented = f"{self.token}{self.length}{TERMINATOR}{TERMINATOR.join(converted_values)}"
        if not self.skip_terminator:
            represented+=TERMINATOR
        return represented

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
    def __init__(self, values):
        self.length = len(values)
        if isinstance(values,dict):
            values = TERMINATOR.join([f"{k}:{v}" for k,v in values.items()])
            self.length = len(values)
        super().__init__("$",[values])

class NullBulkString(SimpleRESP):
    def __init__(self, _=""):
        super().__init__("$","-1")

class Array(AggregateRESP):
    def __init__(self, values):
        super().__init__("*", values)
        self.length = len(values)
        self.skip_terminator=True