"""A collection of metadata Taggers for a variety of media types"""
import os
import re
import shutil
import string
import subprocess

import trakt
import itunes
import requests

from subler import Subler
from subler.tools import AtomCollection

from trakt.tv import TVShow
from trakt.movies import Movie

from .utils import ignored, move_to_trash, strip_unicode
# from .artwork import generate_artwork
from .parsers import *
from .searchers import (TraktTVSearcher, ITunesSeasonSearcher,
                        ITunesEpisodeSearcher)

__author__ = 'Jon Nappi'
__all__ = ['Tagger', 'TVTagger', 'MovieTagger', 'MusicTagger']

TV_GENREIDS = {'Comedy': 4000, 'Drama': 4001, 'Animation': 4002,
               'Action & Adventure': 4003, 'Classic': 4004, 'Kids': 4005,
               'Nonfiction': 4006, 'Reality TV': 4007,
               'Sci-Fi & Fantasy': 4008, 'Sports': 4009, 'Teens': 4010,
               'Latino TV': 4011}

MOVIE_GENREIDS = {'Action & Adventure': 4401, 'Anime': 4402, 'Classics': 4403,
                  'Comedy': 4404, 'Documentary': 4405, 'Drama': 4406,
                  'Foreign': 4407, 'Horror': 4408, 'Independent': 4409,
                  'Kids & Family': 4410, 'Musicals': 4411, 'Romance': 4412,
                  'Sci-Fi & Fantasy': 4413, 'Short Films': 4414,
                  'Special Interest': 4415, 'Thriller': 4416, 'Sports': 4417,
                  'Western': 4418, 'Urban': 4419, 'Holiday': 4420,
                  'Made for TV': 4421, 'Concert Films': 4422,
                  'Music Documentaries': 4423, 'Music Feature Films': 4424,
                  'Japanese Cinema': 4425, 'Jidaigeki': 4426,
                  'Tokusatsu': 4427, 'Korean Cinema': 4428}


class Tagger(object):
    """Generic Tagger Class"""
    steps = 2
    searchers = []

    def __init__(self, logger, progress_meter):
        super(Tagger, self).__init__()
        self.logger = logger
        self.progress_meter = progress_meter
        self.file_name = None
        self.output_file = self.file_name
        self.atoms = AtomCollection()
        self.media_kind = 'Movie'
        self.subler = None

    @property
    def output_file_name(self):
        """Stubbed out output_file_name property. To be implemented by
        subclasses
        """
        return None

    def has_artwork(self, url):
        """Attempts to download artwork from the provided URL and write it to a
        .jpg file named '.albumart.jpg' then return True as long as a 2xx HTTP
        response is recieved. If an error should occur, nothing is downloaded
        and False is returned
        """
        self.logger.info('Downloading Album Artwork...\n\tURL: {}'.format(url))
        req = requests.get(url)
        if 200 <= req.status_code < 300:
            file_name = '.albumart{}.jpg'.format(str(os.getpid()))
            with open(file_name, 'w') as f:
                f.write(req.content)
            return True
        message = 'Album Art Not Downloaded: {}'.format(req.status_code)
        self.logger.log(message)
        return False

    def do_tagging(self):
        """Builds the actual AtomicParsley call for the provided file and then
        makes the call to Atomic Parsley to actually write the metadata to the
        file.
        """
        self._update_progress()
        tmp_file_name = '.tmp{}.m4v'.format(str(os.getpid()))
        full_path = os.path.abspath(tmp_file_name)
        subler = Subler(self.file_name, dest=full_path,
                        media_kind=self.media_kind, metadata=self.atoms.atoms)

        # if 'Artwork' not in self.atoms:
        #     self.atoms['Artwork'] = generate_artwork(self.atoms['Artist'],
        #                                              self.atoms['Album'])

        self.logger.info('Beginning Metadata tagging...')
        try:
            subler.tag()
        except subprocess.CalledProcessError as ex:
            if ex.returncode != 255:
                raise ex
        self.logger.info('Metadata tagging complete. moving updated file')

        for tag, value in self.atoms.items():
            if tag == 'Artwork' and os.path.exists(value):
                os.remove(value)
        move_to_trash(self.file_name)
        file_name = unicode(os.path.basename(self.file_name))
        dest_path = self.file_name.replace(file_name, self.output_file_name)
        shutil.move(full_path, dest_path)
        self._update_progress()

    def _update_progress(self):
        """Grab the lock for our "progress_meter" (shared memory float) and
        update it by 1
        """
        with self.progress_meter.get_lock():
            self.progress_meter.value += 1.0


class TVTagger(Tagger):
    """Tagger Subclass tailored to tagging TV Show metadata"""
    steps = 2 + 10
    searchers = [TraktTVSearcher]

    def __init__(self, file_name, logger, progress_meter, customs=None):
        super(TVTagger, self).__init__(logger, progress_meter)
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name
        self.customs = customs or {}
        trakt.api_key = customs.get('trakt_key', '')
        self.media_kind = 'TV Show'
        self.atoms = AtomCollection()
        self.atoms['Comments'] = ''
        self.atoms['Disk #'] = '1/1'
        self.subler = Subler(self.file_name, optimize=False,
                             media_kind=self.media_kind)
        self._output_file = u'{episode} {title}.m4v'

        self._update_progress()

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        episode = self.atoms['TV Episode #']
        if episode < 10:
            episode = '0{}'.format(episode)
        return self._output_file.format(episode=episode,
                                        title=self.atoms['Name'])

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        self._update_progress()

        for key, val in self.customs.items():
            self.atoms[key] = val

        extension = os.path.splitext(self.file_name)[-1].lower()
        if extension not in self.supported_types:
            self.logger.error(u'Unsupported file type: {}'.format(extension))
            return
        my_parser = TVParser(self.file_name)
        show, season, episode, title = my_parser.parse()

        self.atoms['Name'], self.atoms['TV Season'] = title, season
        for tag in ['Artist', 'Album Artist', 'TV Show']:
            self.atoms[tag] = os.path.basename(show)
        self.atoms['TV Episode #'] = self.atoms['Track #'] = episode
        self.atoms['TV Episode ID'] = 'S{}E{}'.format(season, episode)
        # Format album name
        artist = self.atoms.get('Artist', '')
        album_title = u'{}, Season {}'.format(artist, season)
        self.atoms['Album'] = album_title

        self._update_progress()

        TraktTVSearcher(self.atoms).search(query=self.atoms['TV Show'])
        season_query = u'{} {}'.format(artist, season)
        query_title = unicode(self.atoms['Name']).lower().replace('-', ' ').strip()
        episode_query = u'{} {}'.format(os.path.basename(show), query_title)
        ITunesSeasonSearcher(self.atoms).search(query=season_query)
        ITunesEpisodeSearcher(self.atoms).search(query=episode_query)
        TraktTVSearcher(self.atoms).search(query=self.atoms['TV Show'])

        if 'Artwork_URL' in self.atoms:
            url = self.atoms.pop('Artwork_URL')
            if self.has_artwork(url):
                pid = str(os.getpid())
                art = os.path.abspath('.albumart{}.jpg'.format(pid))
                self.atoms['Artwork'] = art.replace(' ', '\\ ')
        if 'Content Rating' in self.atoms:
            self.subler.rating = self.atoms.pop('Content Rating')

        self.do_tagging()


class MusicTagger(Tagger):
    """Tagger Subclass tailored to tagging Music metadata"""
    steps = 2 + 6

    def __init__(self, file_name, logger, progress_meter, customs=None):
        super(MusicTagger, self).__init__(logger, progress_meter)
        self.supported_types = ['.m4a']
        self.file_name = file_name
        self.customs = customs or {}
        self.media_kind = 'Music'
        self.atoms = AtomCollection()
        self.atoms['Comments'] = ''
        self.atoms['Disk #'] = '1/1'
        self.subler = Subler(self.file_name, media_kind=self.media_kind)
        self._output_file = u'{track} {title}.m4a'
        self._update_progress()

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        track = str(self.atoms['Track #']).split('/')[0]
        if int(track) < 10:
            track = '0{}'.format(track)
        return self._output_file.format(track=track, title=self.atoms['Name'])

    def do_itunes_search(self, query):
        """This method uses the provided query for performing an iTunes audio
        track search
        """
        self._update_progress()

        results = itunes.search_track(query)
        track = None
        for result in results:
            right_name = self.atoms['Name'] in result.get_name()
            right_artist = self.atoms['Artist'] == result.get_artist().name
            if right_name and right_artist:
                track = result
                break
        if track:
            # Album
            self.atoms['Album'] = track.get_album()
            # Albumart
            url = track.get_artwork()
            url = string.replace(url['60'], '60x60-50', '600x600-75')
            if self.has_artwork(url):
                pid = str(os.getpid())
                art = os.path.abspath('.albumart{}.jpg'.format(pid))
                self.atoms['Artwork'] = art.replace(' ', '\\ ')
            # Genre
            self.atoms['Genre'] = track.get_genre()
            album = track.get_album()
            self.atoms['Copyright'] = album.copyright
            self.atoms['Track #'] = '{}/{}'.format(self.atoms['Track #'],
                                                   album.get_track_count())
            self.atoms['Release Date'] = album.get_release_date_raw()
            self.atoms['Album Artist'] = self.atoms['Artist']
            self.atoms['contentID'] = track.get_id()
            if track.json['trackExplicitness'].lower() == 'explicit':
                self.subler.explicitness = 'Explicit'

            self._update_progress()

            self.do_tagging()
        else:
            self.logger.error(u'{} not found in iTunes'.format(query))
            self._update_progress()

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        self._update_progress()
        for key, val in self.customs.items():
            self.atoms[key] = val

        extension = os.path.splitext(self.file_name)[-1].lower()
        if extension not in self.supported_types:
            msg = '{} given to be tagged, but {} is not a supported file type'
            self.logger.error(msg.format(self.file_name, extension))
            return
        my_parser = MusicParser(self.file_name)
        artist, album, track, title = my_parser.parse()

        self.atoms['Artist'] = artist
        self.atoms['Album'] = album
        self.atoms['Track #'] = track
        self.atoms['Name'] = title
        query = u'{} {}'.format(artist, title)
        self._update_progress()
        self.do_itunes_search(query)
        self._update_progress()
        self.do_tagging()


class MovieTagger(Tagger):
    """Tagger Subclass tailored to tagging Movie metadata"""
    steps = 2 + 10

    def __init__(self, file_name, logger, progress_meter, customs=None):
        super(MovieTagger, self).__init__(logger, progress_meter)
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name
        self.customs = customs or {}
        trakt.api_key = customs.get('trakt_key', '')
        self.atoms = AtomCollection()
        self.atoms['Comments'] = ''
        self.atoms['Disk #'] = '1/1'
        self.subler = Subler(self.file_name, media_kind=self.media_kind)
        self._output_file = u'{title}.m4v'
        self._update_progress()

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        return self._output_file.format(title=self.atoms['Name'])

    def do_itunes_search(self):
        """This method pulls the title of the current Movie out of the
        parameters dictionary. This title is then used as the query for an
        iTunes movie search
        """
        self._update_progress()
        self.logger.info('Performing iTunes Search')
        movie_results = itunes.search_movie(self.atoms['Name'])
        table = string.maketrans('', '')
        movie_data = None
        for result in movie_results:
            result_name = result.get_name().lower()
            result_name = result_name.translate(table, string.punctuation)
            result_name = string.replace(result_name, '  ', ' ')
            title = self.atoms['Name'].lower()
            title = title.translate(string.maketrans('', ''),
                                    string.punctuation)
            title = string.replace(title, '  ', ' ')
            if result_name == title:
                self.atoms['Name'] = strip_unicode(result.get_name())
                movie_data = result
        if movie_data is None:
            for result in movie_results:
                if result.get_name().lower() == self.atoms['Name'].lower():
                    self.atoms['Name'] = strip_unicode(result.get_name())
                    movie_data = result
                    break
                else:
                    words = self.atoms['Name'].lower().translate(
                        string.maketrans('', ''), string.punctuation).split(' ')
                    total = len(words)
                    matches = 0
                    result_words = result.get_name().lower().translate(
                        string.maketrans('', ''), string.punctuation).split(' ')
                    for word in words:
                        if word in result_words:
                            matches += 1
                    if float(matches) / float(total) > 0.8:
                        movie_data = result
                        break
        self._update_progress()
        with ignored(Exception):
            # Artwork
            url = movie_data.get_artwork()
            url = string.replace(url['60'], '60x60-50', '600x600-75')
            if self.has_artwork(url):
                pid = str(os.getpid())
                art = os.path.abspath('.albumart{}.jpg'.format(pid))
                self.atoms['Artwork'] = art.replace(' ', '\\ ')
            json = movie_data.json
            # Content Rating
            self.subler.rating = json['contentAdvisoryRating']
            # Explcitness
            ex = json['trackExplicitness']
            self.subler.explicitness = ex if ex == 'Explicit' else 'Clean'
            # Description
            self.atoms['Long Description'] = \
                strip_unicode(json['longDescription'])
            self.atoms['Description'] = self.atoms['Long Description'][:250]
            if self.atoms['Description'].count('"') % 2 != 0:
                self.atoms['Description'] += '"'
            # Genre
            self.atoms['Genre'] = json['primaryGenreName']
            # Release Date
            self.atoms['Release Date'] = json['releaseDate']
            # Genre ID
            self.atoms['genreID'] = MOVIE_GENREIDS[self.atoms['Genre']]
            # Catalog ID
            self.atoms['contentID'] = movie_data.get_id()
        self._update_progress()

    def do_trakt_search(self):
        """Search Trakt.TV for data on the movie being tagged"""
        self._update_progress()
        title = self.atoms['Name']
        year = None
        if '(' in title and ')' in title:
            year = title[title.find('(')+1:title.find(')')].strip()
            title = ' '.join(title.split()[:-1]).strip()
        movie = Movie(title, year=year)
        self.subler.rating = movie.certification
        self.atoms['Genre'] = movie.genres[0].name
        self.atoms['Description'] = self.atoms['Long Description'] = \
            movie.overview
        self.atoms['Release Date'] = movie.released_iso
        self.atoms['Name'] = movie.title
        if 'Artwork' not in self.atoms and 'poster' in movie.images:
            if self.has_artwork(movie.images['poster']):
                pid = str(os.getpid())
                art = os.path.abspath('.albumart{}.jpg'.format(pid))
                self.atoms['Artwork'] = art.replace(' ', '\\ ')
        self._update_progress()

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        self._update_progress()
        for key, val in self.customs.items():
            self.atoms[key] = val

        vid = self.file_name
        extension = os.path.splitext(vid)[-1].lower()
        if extension not in self.supported_types:
            msg = '{} given to be tagged, but {} is not a supported file type'
            self.logger.error(msg.format(vid, extension))
            return
        self.logger.info(u'Tagging {}'.format(os.path.basename(vid)))
        # Title
        self.atoms['Name'] = os.path.basename(vid).replace('\\',
                                                           '').strip()[:-4]
        self._update_progress()
        self.do_itunes_search()
        self._update_progress()
        self.do_trakt_search()
        self._update_progress()
        self.do_tagging()
