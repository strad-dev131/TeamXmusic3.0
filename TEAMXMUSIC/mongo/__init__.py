# Mongo package initialization
from .afkdb import *
from .couples_db import *
from .pretenderdb import *
from .welcomedb import *

__all__ = [
    "add_afk", "is_afk", "remove_afk",  # from afkdb
]
