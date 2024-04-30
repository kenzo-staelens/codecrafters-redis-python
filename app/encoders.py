TERMINATOR = "\r\n"

class SimpleRESP:
    def __init__(self, token):
        self.token=token
    
    @property
    def encoded(self):
        return f"{self.token}{self.value}{TERMINATOR}"
    
    @encoded.setter
    def encoded(self,_):
        pass

class SimpleString(SimpleRESP):
    def __init__(self, value):
        super.__init__(self,"+")
        self.value = value
    
    
class SimpleError(SimpleRESP):
    def __init__(self, value):
        super().__init__("-")
        self.value = value

class Integer(SimpleRESP):
    def __init__(self, value):
        super().__init__(":")
        self.value = value

class Null(SimpleRESP):
    def __init__(self, _):
        super().__init__("_")
        self.value = ""

class Boolean(SimpleRESP):
    def __init__(self, value):
        super().__init__("#")
        self.value = value

class Double(SimpleRESP):
    def __init__(self, value):
        super().__init__(",")
        self.value = value

class BigNumber(SimpleRESP):
    def __init__(self, value):
        super().__init__("(")
        self.value = value