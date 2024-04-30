TERMINATOR = "\r\n"

class SimpleRESP:
    def __init__(self, token,value):
        self.token=token
        self.value = value
    
    @property
    def encoded(self):
        return f"{self.token}{self.value}{TERMINATOR}"
    
    @encoded.setter
    def encoded(self,_):
        pass

    def encode(self, format):
        return self.encoded.encode(format)

    def __repr__(self) -> str:
        return self.encoded()

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
    def __init__(self, _):
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