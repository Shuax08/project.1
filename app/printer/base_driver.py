from flask import render_template
from app.models import db,Shop
class BasePrinterDriver:
    def print_text(self,text): raise NotImplementedError
class NullPrinterDriver(BasePrinterDriver):
    def print_text(self,text): return False
class NetworkPrinterDriver(BasePrinterDriver):
    def __init__(self,host,port=9100): self.host,self.port=host,port
    def print_text(self,text):
        import socket
        with socket.create_connection((self.host,self.port),timeout=3) as s:s.sendall(text.encode())
        return True
