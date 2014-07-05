try:
    from .utils import *
    from .taggers import *
except ImportError:
    # Don't let dependencies stop us from importing on install
    pass

version_info = (1, 0, 9)

__name__ = 'pytagger'
__doc__ = 'A python backend to iTunes style metadata tagging'
__author__ = 'Jonathan Nappi'
__version__ = '.'.join([str(x) for x in version_info])
__license__ = 'GPL'
__maintainer__ = 'Jonathan Nappi'
__email__ = 'moogar@comcast.net'
__status__ = 'Beta'
__title__ = '{} version {}'.format(__name__, __version__)
