def classFactory(iface):
    from .tool import NetworkManagerTool
    return NetworkManagerTool(iface)
