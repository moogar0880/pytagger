# -*- coding: utf-8 -*-
from pytagger.taggers import TVTagger, MovieTagger, MusicTagger  # NOQA

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
