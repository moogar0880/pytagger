"""A collection of metadata Taggers for a variety of media types"""
import os
import re
import string
import logging
import subprocess

from datetime import date

import trakt
import itunes
import requests

from subler import Subler
from trakt.tv import TVShow
from trakt.movies import Movie

from .utils import *
from .parsers import *

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
    def __init__(self):
        super(Tagger, self).__init__()
        log_date = date.today().isoformat()
        home = os.path.expanduser('~')
        name = os.path.join(home, '.pytagger_logs/{}{}.log'.format(__name__,
                                                                   log_date))
        if not os.path.exists(os.path.join(home, '.pytagger_logs')):
            os.mkdir(os.path.join(home, '.pytagger_logs'))
        logging.basicConfig(filename=name, level=logging.CRITICAL,
                            format='%(asctime)s %(levelname)s:%(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S %p')
        self.logger = logging.getLogger(__name__)
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
        tmp_file_name = '.tmp{}.m4v'.format(str(os.getpid()))
        full_path = os.path.abspath(tmp_file_name).replace(' ', '\\ ')
        subler = Subler(self.file_name.replace(' ', '\\ '), dest=full_path,
                        media_kind=self.media_kind, metadata=self.atoms.atoms)

        self.logger.info('Beginning Metadata tagging...')
        try:
            subler.tag()
        except subprocess.CalledProcessError as ex:
            if ex.returncode != 255:
                raise ex
        self.logger.info('Metadata tagging complete. moving updated file')

        for tag, value in self.atoms.items():
            if tag == 'Artwork' and os.path.exists(value):
                subprocess.check_call('rm {}'.format(value), shell=True)
        move_to_trash(self.file_name)
        file_name = os.path.basename(self.file_name)
        dest_path = self.file_name.replace(file_name, self.output_file_name)
        command = 'mv {} "{}"'.format(full_path, dest_path)
        subprocess.check_call(command, shell=True)


class TVTagger(Tagger):
    """Tagger Subclass tailored to tagging TV Show metadata"""
    def __init__(self, file_name, customs=None, auto_tag=True):
        super(TVTagger, self).__init__()
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name
        self.customs = customs or {}
        trakt.api_key = customs.pop('trakt_key', '')
        self.media_kind = 'TV Show'
        self.atoms = AtomCollection()
        self.atoms['Comments'] = ''
        self.atoms['Disk #'] = '1/1'
        self.subler = Subler(self.file_name, optimize=False,
                             media_kind=self.media_kind)
        self._output_file = '{episode} {title}.m4v'

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        episode = self.atoms['TV Episode #']
        if episode < 10:
            episode = '0{}'.format(episode)
        return self._output_file.format(episode=episode,
                                        title=self.atoms['Name'])

    def do_itunes_search(self, queries):
        """This method pulls the provided queries out of their list and then
        uses them as the queries for their respective iTunes searches
        """
        parameters = {}
        search = queries['season']
        self.logger.info('Searching iTunes for {}'.format(search))
        # Gather Season information
        season_results = itunes.search_season(search)
        season_data = None
        with ignored(AttributeError):
            # Get season data from iTunes
            if season_results:
                title_comparator = re.sub(r'\W+', ' ', self.atoms['TV Show'])
                for res in season_results:
                    comparative_title = re.sub(r'\W+', ' ', res.artist.name)
                    if title_comparator.lower() == comparative_title.lower() \
                            and self.atoms['Album'] in res.get_album().name:
                        season_data = res
                        break
                # Copyright info
                parameters['Copyright'] = season_data.get_copyright()
                url = season_data.get_artwork()
                url = string.replace(url['60'], '60x60-50', '600x600-75')
                if self.has_artwork(url):
                    pid = str(os.getpid())
                    art = os.path.abspath('.albumart{}.jpg'.format(pid))
                    parameters['Artwork'] = art.replace(' ', '\\ ')
            if season_data is None:
                self.logger.debug('{} not found in iTunes'.format(search))

        #Gather episode information
        search = queries['episode']
        self.logger.info('Searching iTunes for {}'.format(search))
        episode_results = itunes.search_episode(search)
        episode_data = None
        if episode_results:
            episode_data = episode_results[0]
        else:
            self.logger.debug('{} not found in iTunes'.format(search))
        with ignored(AttributeError):
            # Genre
            parameters['Genre'] = episode_data.get_genre()
            # Genre ID
            parameters['genreID'] = TV_GENREIDS[parameters['Genre']]
            # Release Date
            parameters['Release Date'] = episode_data.get_release_date()
            # short description, max length 255 characters
            description = episode_data.get_short_description().strip()[:255]
            description = string.replace(description, '\n', '')
            parameters['Description'] = strip_unicode(description)
            # long description
            ldesc = 'Long Description'
            parameters[ldesc] = episode_data.get_long_description().strip()
            # iTunes Catalog ID
            parameters['contentID'] = episode_data.get_episodeID()
            # Content Rating
            self.subler.rating = episode_data.get_content_rating()
        return parameters

    def do_trakt_search(self):
        """Search Trakt.TV for data on the episode being tagged"""
        show_name = self.atoms['TV Show']
        season_num = int(self.atoms['TV Season'])
        if int(self.atoms.get('TV Episode #', 0)) != 0:
            episode_num = int(self.atoms['TV Episode #']) - 1
        else:
            episode_num = int(self.atoms['TV Episode #'])
        msg = '{} : {} : {}'.format(show_name, season_num, episode_num)
        self.logger.warning(msg)
        show = TVShow(show_name)
        episode = show.search_season(season_num).episodes[episode_num]

        self.atoms['Rating'] = show.certification
        self.atoms['Genre'] = show.genres[0].name
        self.atoms['TV Network'] = show.network
        actors = []
        for actor in show.people:
            if hasattr(actor, 'name'):
                actors.append(actor.name)
        self.atoms['Cast'] = ', '.join([actor for actor in actors if actor is not None])
        self.atoms['Release Date'] = episode.first_aired_iso
        if len(episode.overview) > 250:
            self.atoms['Description'] = episode.overview[:250]
        else:
            self.atoms['Description'] = episode.overview
        self.atoms['Long Description'] = episode.overview

        self.atoms['TV Show'] = episode.show
        self.atoms['Artist'] = episode.show

        self.atoms['Name'] = episode.title
        # Reformat fields
        self.atoms['Album Artist'] = episode.show
         # Reformat album name
        self.atoms['Album'] = '{}, Season {}'.format(self.atoms['Artist'],
                                                     self.atoms['TV Season'])
        if self.atoms['Genre'] in TV_GENREIDS:
            self.atoms['genreID'] = TV_GENREIDS[self.atoms['Genre']]

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        for key, val in self.customs.items():
            self.atoms[key] = val

        extension = os.path.splitext(self.file_name)[-1].lower()
        if extension not in self.supported_types:
            self.logger.error('Unsupported file type: {}'.format(extension))
            return
        my_parser = TVParser(self.file_name)
        show, season, episode, title = my_parser.parse()

        # name of episode
        self.atoms['Name'] = title
        # season number
        self.atoms['TV Season'] = season
        # name of show
        for tag in ['Artist', 'Album Artist', 'TV Show']:
            self.atoms[tag] = os.path.basename(show)
        # Episode number
        self.atoms['TV Episode #'] = self.atoms['Track #'] = episode

        # Format episode ID
        ep_id = 'S{}E{}'.format(season, episode)
        self.atoms['TV Episode ID'] = ep_id
        # Format album name
        artist = self.atoms.get('Artist', '')
        album_title = '{}, Season {}'.format(artist, season)
        self.atoms['Album'] = album_title

        self.do_trakt_search()
        # Build queries for iTunes search
        tmp = dict()
        tmp['season'] = '{} {}'.format(artist, season)
        query_title = self.atoms['Name'].lower()
        query_title = string.replace(query_title, '-', ' ').strip()
        if 'part ' in query_title:
            query_title = string.replace(query_title, 'part ', 'pt ')
        if 'pt i' in query_title:
            query_title = string.replace(query_title, 'pt i', 'pt 1')
        if 'pt ii' in query_title:
            query_title = string.replace(query_title, 'pt ii', 'pt 2')
        if 'pt iii' in query_title:
            query_title = string.replace(query_title, 'pt iii', 'pt 3')
        if 'fuckers' in query_title:
            query_title = string.replace(query_title, 'fuckers', 'fu*kers')
        if 'fucker' in query_title:
            query_title = string.replace(query_title, 'fucker', 'f*****')
        if 'fuck' in query_title:
            query_title = string.replace(query_title, 'fuck', 'f***')
        tmp['episode'] = '{} {}'.format(os.path.basename(show), query_title)
        # Concatenate parameters with iTunes query results
        for key, val in self.do_itunes_search(tmp).items():
            self.atoms[key] = val

        self.do_trakt_search()
        self.do_tagging()


class MusicTagger(Tagger):
    """Tagger Subclass tailored to tagging Music metadata"""
    def __init__(self, file_name, customs=None, auto_tag=True):
        super(MusicTagger, self).__init__()
        self.supported_types = ['.m4a']
        self.file_name = file_name
        self.customs = customs or {}
        self.media_kind = 'Music'
        self.atoms = AtomCollection()
        self.atoms['Comments'] = ''
        self.atoms['Disk #'] = '1/1'
        self.subler = Subler(self.file_name, media_kind=self.media_kind)
        self._output_file = '{track} {title}.m4a'

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
            self.do_tagging()
        else:
            self.logger.error('{} not found in iTunes'.format(query))

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
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
        query = '{} {}'.format(artist, title)
        self.do_itunes_search(query)
        self.do_tagging()


class MovieTagger(Tagger):
    """Tagger Subclass tailored to tagging Movie metadata"""
    def __init__(self, file_name, customs=None, auto_tag=True):
        super(MovieTagger, self).__init__()
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name
        self.customs = customs or {}
        trakt.api_key = customs.pop('trakt_key', '')
        self.atoms = AtomCollection()
        self.atoms['Comments'] = ''
        self.atoms['Disk #'] = '1/1'
        self.subler = Subler(self.file_name, media_kind=self.media_kind)
        self._output_file = '{title}.m4v'

    @property
    def output_file_name(self):
        """The formatted output file representation"""
        return self._output_file.format(title=self.atoms['Name'])

    def do_itunes_search(self):
        """This method pulls the title of the current Movie out of the
        parameters dictionary. This title is then used as the query for an
        iTunes movie search
        """
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

    def do_trakt_search(self):
        """Search Trakt.TV for data on the movie being tagged"""
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

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        for key, val in self.customs.items():
            self.atoms[key] = val

        vid = self.file_name
        extension = os.path.splitext(vid)[-1].lower()
        if extension not in self.supported_types:
            msg = '{} given to be tagged, but {} is not a supported file type'
            self.logger.error(msg.format(vid, extension))
            return
        self.logger.info('Tagging {}'.format(os.path.basename(vid)))
        # Title
        self.atoms['Name'] = os.path.basename(vid).replace('\\',
                                                           '').strip()[:-4]
        self.do_itunes_search()
        self.do_trakt_search()
        self.do_tagging()
