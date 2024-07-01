"""Top-level package for the project."""

__version__ = "0.1.0"

all = ["version"]


def version():
    """
    Version of the code

    :rtype: str
    """
    return __version__


from .core import *
from .sk import *
from .iqrmrfi import *