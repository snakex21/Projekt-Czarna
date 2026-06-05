"""Pomocnicze funkcje sieciowe launchera."""

import socket


__all__ = ["get_local_ip"]


def get_local_ip():
    """Pobiera lokalny adres IP komputera."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"
