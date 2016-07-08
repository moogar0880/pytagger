# -*- coding: utf-8 -*-
"""A collection of metadata Taggers for a variety of media types"""
import asyncio
import os
import shutil
import subprocess

from asyncio.log import logger as LOGGER
from uuid import uuid4
from osx_trash import trash
from subler import Subler, Atom
from subler.tools import AtomCollection

from pytagger.parsers import TVParser, MusicParser, MovieParser
from pytagger.searchers import (TraktTVSearcher, TraktMovieSearcher,
                                ITunesSeasonSearcher, ITunesEpisodeSearcher,
                                ITunesMovieSearcher, ITunesMusicSearch)

__author__ = 'Jon Nappi'
__all__ = ['Tagger', 'TVTagger', 'MovieTagger', 'MusicTagger']


class Tagger(object):
    """Generic Tagger Class"""
    PARSER = None
    searchers = tuple()
    supported_types = tuple()
    media_kind = 'Movie'
    output_file_fmt = None

    def __init__(self, file_name, customs=None, apple_id=None, trakt_key=None):
        super(Tagger, self).__init__()
        self.file_name = file_name
        self.trakt_key = trakt_key
        self.customs = customs or {}
        self.output_file = self.file_name
        self.atoms = AtomCollection()
        self.atoms['Comments'] = ''
        self.atoms['Disk #'] = '1/1'
        if apple_id:
            self.atoms['iTunes Account'] = apple_id
        for key, val in self.customs.items():
            self.atoms[key] = val
        self.parser = self.PARSER(self.file_name)

    @property
    def output_file_name(self):
        """Stubbed out output_file_name property. To be implemented by
        subclasses
        """
        raise NotImplementedError()

    @asyncio.coroutine
    def tag(self):
        """Builds the actual AtomCollection data set for the provided file and
        then makes the call to Subler to actually write that metadata to the
        file.
        """
        extension = os.path.splitext(self.file_name)[-1].lower()
        if extension not in self.supported_types:
            raise KeyError('Unsupported file type: {}'.format(extension))

        for searcher in self.searchers:
            searcher(self.atoms).search(self.parser)

        tmp_file_name = '.tmp{}.m4v'.format(str(uuid4()))
        full_path = os.path.abspath(tmp_file_name)

        # determine explicitness
        explicit = self.atoms.pop('_explicit', Atom('', ''))
        if explicit.value.lower() != 'explicit':
            explicit = None
        else:
            explicit = explicit.value

        # create a subler instance for writing collected metadata to file
        subler = Subler(self.file_name, dest=full_path, explicit=explicit,
                        media_kind=self.media_kind, metadata=self.atoms.atoms)

        LOGGER.info('Beginning Metadata tagging...')
        import pdb; pdb.set_trace()
        try:
            subler.tag()
        except subprocess.CalledProcessError as ex:
            if ex.returncode != 255:
                raise ex
        LOGGER.info('Metadata tagging complete. moving updated file')

        for tag, value in self.atoms.items():
            if tag == 'Artwork' and os.path.exists(value):
                os.remove(value)
        trash(self.file_name)
        file_name = os.path.basename(self.file_name)
        dest_path = self.file_name.replace(file_name, self.output_file_name)
        shutil.move(full_path, dest_path)


class TVTagger(Tagger):
    """Tagger Subclass tailored to tagging TV Show metadata"""
    PARSER = TVParser
    searchers = (ITunesSeasonSearcher, ITunesEpisodeSearcher, TraktTVSearcher)
    media_kind = 'TV Show'
    supported_types = ('.mp4', '.m4v')
    output_file_fmt = '{episode} {title}.m4v'

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        episode = self.atoms['TV Episode #']
        if episode < 10:
            episode = '0{}'.format(episode)
        return self.output_file_fmt.format(episode=episode,
                                           title=self.atoms['Name'])


class MusicTagger(Tagger):
    """Tagger Subclass tailored to tagging Music metadata"""
    PARSER = MusicParser
    searchers = (ITunesMusicSearch,)
    supported_types = ('.m4a',)
    output_file_fmt = '{track} {title}.m4a'

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        track = str(self.atoms['Track #']).split('/')[0]
        if int(track) < 10:
            track = '0{}'.format(track)
        return self.output_file_fmt.format(track=track,
                                           title=self.atoms['Name'])


class MovieTagger(Tagger):
    """Tagger Subclass tailored to tagging Movie metadata"""
    PARSER = MovieParser
    searchers = (ITunesMovieSearcher, TraktMovieSearcher)
    supported_types = ('.mp4', '.m4v')
    output_file_fmt = '{title}.m4v'

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        return self.output_file_fmt.format(title=self.atoms['Name'])
