# -*- coding: utf-8 -*-
"""A collection of custom parsers designed to pull out relevant information
about various kinds of media files.
"""
import os
import re

__author__ = 'Jon Nappi'
__all__ = ['TVParser', 'MusicParser', 'MovieParser']


class BaseParser(object):
    """Base media info parser."""
    patterns = tuple()

    def __init__(self, file_path):
        """Create a :class:`BaseParser`"""
        self.file_path = file_path

    def parse(self):
        """Base no-op parse method, to be implemented by all subclasses"""
        raise NotImplementedError()


class TVParser(BaseParser):
    """Custom parser subclass for parsing data out of TV Episode filenames.
    Currently all of the following patterns are matched:
    ====================   ====================================
    Pattern                Example
    ====================   ====================================
    (\d+)\s+(.+)           01 Pilot.m4v
    ([.\w]+)S(\d+)E(\d+)   Royal.Pains.S06E01.HDTV.x264-LOL.m4v
    ([.\w]+).(\d+)         royal.pains.602.HDTV.x264-LOL.m4v
    ====================   ====================================
    """
    def __init__(self, *args, **kwargs):
        """Grab the filepath and create TVParsing patterns"""
        super(TVParser, self).__init__(*args, **kwargs)
        pattern1 = r'(?P<episode>\d+)\s+(?P<title>.+)'
        pattern2 = r'(?P<show>[.\w]+)[S|s](?P<season>\d+)[E|e](?P<episode>\d+)'
        pattern3 = r'(?P<show>[.\w]+)\.(?P<season_ep>\d+)'
        self.patterns = pattern1, pattern2, pattern3

    def parse(self):
        """Iterate over this :class:`TVParser`'s patterns until one sticks. Once
        a pattern is matched it is processed and the results from that
        processing are returned.
        """
        file_name = os.path.basename(self.file_path).replace('\\', '').strip()
        for index, pattern in enumerate(self.patterns):
            match = re.match(pattern, file_name)
            if match is not None:
                method = 'process_p{}'.format(index + 1)
                return getattr(self, method)(match)

    def process_p1(self, match):
        """Process episode data out of a filename matching (\d+)\s+(.+). It's
        important to note that if this pattern is matched the two containing
        directory names will be consumed in order to try and collect season and
        show information, effecitvely assuming an organizational structure
        matching /Show Name/Season #/Episode.ext

        :return: 4-tuple of show, season, episode, title
        """
        sea_name = os.path.dirname(self.file_path).replace('\\', '')
        sho_name = os.path.dirname(
            sea_name).replace('\\', '').split(os.sep)[-1]
        episode, title = match.group('episode'), match.group('title')
        season = int(sea_name.split()[-1])
        return sho_name, season, int(episode), title[:-4]

    def process_p2(self, match):
        """Process episode data out of a filename matching
        ([.\w]+)S(\d+)E(\d+). Unlike pattern1 this process function does not
        assume any kind of pre-existing directory structure for pulling in
        additional information. However, it is important to note that the
        episode's title will not be returned by this method.

        :return: 4-tuple of show, season, episode, None
        """
        show = ' '.join(match.group('show').split('.')).strip()
        season = int(match.group('season'))
        episode = int(match.group('episode'))
        return show, season, episode, None

    def process_p3(self, match):
        """Process episode data out of a filename matching ([.\w]+).(\d+).
        Unlike pattern1, and much like pattern2, this process function does not
        assume any kind of pre-existing directory structure for pulling in
        information. However, it is import to note that the episode's title
        will not be returned by this method.

        :return: 4-tuple of show, season, episode, None
        """
        show = ' '.join(match.group('show').split('.')).strip()
        season_ep_data = match.group('season_ep')
        if len(season_ep_data) == 3:
            season = int(season_ep_data[0])
            episode = int(season_ep_data[1:])
        else:
            season = int(season_ep_data[0:2])
            episode = int(season_ep_data[2:])
        return show, season, episode, None


class MusicParser(BaseParser):
    """Custom parser subclass for parsing data out of TV Episode filenames.
    Currently all of the following patterns are matched:
    ====================   ====================================
    Pattern                Example
    ====================   ====================================
    (\d+)\s+(.+)           01 Are You Ready.mp3
    ====================   ====================================
    """
    def __init__(self, *args, **kwargs):
        """Grab the filepath and create MusicParsing patterns"""
        super(MusicParser, self).__init__(*args, **kwargs)
        pattern1 = r'(?P<track>\d+)\s+(?P<title>.+)'
        self.patterns = pattern1,

    def parse(self):
        """Iterate over this :class:`MusicParser`'s patterns until one sticks.
        Once a pattern is matched it is processed and the results from that
        processing are returned. It's important to note that if this pattern is
        matched the two containing directory names will be consumed in order to
        try and collect season and show information, effecitvely assuming an
        organizational structure matching /Artist/Album/Track.ext

        :return: 4-tuple of artist, album, track, title
        """
        file_name = os.path.basename(self.file_path).replace('\\', '').strip()
        for index, pattern in enumerate(self.patterns):
            match = re.match(pattern, file_name)
            if match is not None:
                album = os.path.dirname(self.file_path).replace('\\', '')
                artist = os.path.dirname(album).replace('\\',
                                                        '').split(os.sep)[-1]
                track, title = match.group('track'), match.group('title')
                album = album.split(os.sep)[-1]
                return artist, album, int(track), title[:-4]


class MovieParser(BaseParser):
    """Custom parser subclass for parsing data out of Movie filenames.
    Currently all of the following patterns are matched:
    ====================   ====================================
    Pattern                Example
    ====================   ====================================
    (.+)\s\((\d+)\)        Alice in Wonderland (2010).m4v
    \s+(.+)\.              Alice in Wonderland.m4v
    ====================   ====================================
    """
    def __init__(self, *args, **kwargs):
        """Grab the filepath and create Movie parsing patterns"""
        super(MovieParser, self).__init__(*args, **kwargs)
        pattern1 = r'(?P<title>.+)\s\((?P<year>\d+)\)'
        pattern2 = r'(?P<title>.+)\.'
        self.patterns = pattern1, pattern2

    def parse(self):
        """Iterate over this :class:`MovieParser`'s patterns until one sticks.
        Once a pattern is matched it is processed and the results from that
        processing are returned.
        """
        file_name = os.path.basename(self.file_path).replace('\\', '').strip()
        for index, pattern in enumerate(self.patterns):
            match = re.match(pattern, file_name)
            if match is not None:
                method = 'process_p{}'.format(index + 1)
                return getattr(self, method)(match)

    def process_p1(self, match):
        """Process movie data out of a filename with an explicitly definted
        year in the filename.

        :return: 2-tuple of title, year
        """
        return match.group('title'), int(match.group('year'))

    def process_p2(self, match):
        """Process movie data out of a filename without an explicitly definted
        year in the filename.

        :return: 2-tuple of title, None
        """
        return match.group('title'), None
