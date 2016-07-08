# -*- coding: utf-8 -*-
try:
    from pytagger.taggers import TVTagger, MovieTagger, MusicTagger  # NOQA
except ImportError as ex:
    # Don't let dependencies stop us from importing on install
    import sys
    if 'install' not in sys.argv:
        raise ex
    pass

version_info = (1, 1, 2)

__name__ = 'pytagger'
__doc__ = 'A python backend to iTunes style metadata tagging'
__author__ = 'Jonathan Nappi'
__version__ = '.'.join([str(x) for x in version_info])
__license__ = 'GPL'
__maintainer__ = 'Jonathan Nappi'
__email__ = 'moogar@comcast.net'
__status__ = 'Beta'
__title__ = '{} version {}'.format(__name__, __version__)
