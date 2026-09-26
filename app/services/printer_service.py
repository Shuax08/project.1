from .base_driver import NullPrinterDriver

def get_printer_driver(settings):
    if not settings or not settings.enabled or not settings.host:return NullPrinterDriver()
    from .base_driver import NetworkPrinterDriver
    return NetworkPrinterDriver(settings.host,settings.port)
