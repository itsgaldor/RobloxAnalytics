"""
Instancia global del rate limiter (slowapi).
Centralizado para evitar imports circulares entre main.py y los routers.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
