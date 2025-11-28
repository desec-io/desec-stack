import socket
from functools import cache


@cache
def gethostbyname_cached(host):
    return socket.gethostbyname(host)
