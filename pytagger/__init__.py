import os
import re
import sys
reload(sys)
sys.setdefaultencoding('utf8')
import itunes
import string
import logging
import requests
import subprocess
import unicodedata
from trakt import configure, TVShow, Movie
from pprint import pformat
from datetime import date
from contextlib import contextmanager

__name__ = 'pytagger'
__doc__ = 'A python backend to iTunes style metadata tagging'
__author__ = 'Jonathan Nappi'
__version__ = '0.6'
__license__ = 'GPL'
__maintainer__ = 'Jonathan Nappi'
__email__ = 'moogar@comcast.net'
__status__ = 'Beta'
__title__ = '{} version {}'.format(__name__, __version__)

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


@contextmanager
def ignored(*exceptions):
    """Context manager to ignore specified exceptions and logging pertinent 
    info

        with ignored(AttributeError):
            a = None
            a.foo()
            # bar() is reached despite a.foo() throwing an AttributeError
            bar()
    """
    logger = logging.getLogger('ignored')
    try:
        yield
    except exceptions:
        logger.info('IGNORING {}'.format(exceptions))


def move_to_trash(file_path):
    """Move the provided file to it's closest Trash folder"""
    uid = os.geteuid()
    disk = file_path.split('/')[1]
    local_trash = os.path.join(os.path.expanduser('~'), '.Trash')
    if disk == 'Users':
        if os.path.exists(local_trash):
            command = 'mv "{}" "{}"'.format(file_path, local_trash)
            subprocess.call(command, shell=True)
        else:
            print 'ERROR: Can not find Trash'
    elif disk == 'Volumes':
        dirs = file_path.split('/')
        volume_trash = os.path.join(dirs[1], dirs[2], '.Trashes')
        if os.path.exists(volume_trash):
            users_volume_trash = os.path.join(volume_trash, str(uid))
            if os.path.exists(users_volume_trash):
                subprocess.call('mv "{}" "{}"'.format(file_path,
                                                      users_volume_trash),
                                shell=True)
            else:
                os.mkdir(users_volume_trash)
                subprocess.call('mv "{}" "{}"'.format(file_path,
                                                      users_volume_trash),
                                shell=True)
        elif os.path.exists(local_trash):
            subprocess.call('mv "{}" "{}"'.format(file_path, local_trash),
                            shell=True)
        else:
            print 'ERROR: Can not find Trash'
        subprocess.call('mv "{}" "{}"'.format(file_path, local_trash),
                        shell=True)


def dict_concat(d1, d2):
    """Universal dictionary concatenater.
    WARNING: Assumes that all key values will be unique
    """
    for key in d2.keys():
        d1[key] = d2[key]
    return d1


def get_xml_entry(name):
    """Get the XML formatted name"""
    start = '\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>'
    end = '</string>\n\t\t</dict>\n'
    return start + name + end


def strip_unicode(message):
    """Strip unicode characters from strings. Useful for descriptions and
    titles, which by default get returned from iTunes as unicode strings.
    """
    if type(message) == unicode:
        output = ''
        for ch in message:
            if unicodedata.normalize('NFKD', ch).encode('ascii', 'ignore') == '':
                if ch == u'\u2019':
                    output += "'"
            else:
                output += unicodedata.normalize('NFKD', ch).encode('ascii',
                                                                   'ignore')
        return output
    else:
        return message


def create_itunes_xml(cast, directors, producers, writers):
    """Function for generating the rDNSatom XML data required for iTunes style
    metadata to be able to list the actors, directors, producers, and writers
    for any video media type to be tagged
    """
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD\ PLIST\ 1.0//EN" {}>
<plist version="1.0">
<dict>
""".format('"http://www.apple.com/DTDs/PropertyList-1.0.dtd"')
    if cast is not None and cast != []:
        xml += '\t<key>cast</key>\n\t<array>\n'
        for name in cast:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += '\t</array>\n'

    if directors is not None and directors != []:
        xml += '\t<key>directors</key>\n\t<array>\n'
        for name in directors:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += '\t</array>\n'

    if producers is not None and producers != []:
        xml += '\t<key>producers</key>\n\t<array>\n'
        for name in producers:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += '\t</array>\n'

    if writers is not None and writers != []:
        xml += '\t<key>screenwriters</key>\n\t<array>\n'
        for name in writers:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += '\t</array>\n'

    xml += '</dict>\n</plist>'
    return xml


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
        self.params = dict()

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
            f = open(file_name, 'w')
            f.write(req.content)
            f.close()
            return True
        else:
            message = 'Album Art Not Downloaded: {}'.format(req.status_code)
            self.logger.log(message)
            return False

    def do_tagging(self):
        """Builds the actual AtomicParsley call for the provided file and then
        makes the call to Atomic Parsley to actually write the metadata to the
        file.
        """
        tmp_file_name = '.tmp{}.m4v'.format(str(os.getpid()))
        if 'artwork' in self.params.keys():
            command = 'AtomicParsley "{}" --artwork REMOVE_ALL --output "{}"'
        else:
            command = 'AtomicParsley "{}" --output "{}"'
        command = command.format(self.file_name, tmp_file_name)
        keys = self.params.keys()
        for key in keys:
            if key == 'rDNSatom':
                command += ' --' + key + ' "' + str(self.params[key]) + \
                           '" name=iTunMOVI domain=com.apple.iTunes'
            else:
                command += ' --' + key + ' "' + str(self.params[key]) + '\"'
        # Need to prevent Non-zero exit status 2 AP errors from halting the 
        # entire program
        try:
            null = open(os.devnull)
            self.logger.info('Beginning Metadata tagging...')
            subprocess.check_call(command, shell=True, stdout=null)
            self.logger.info('Metadata tagging complete. moving updated file')
            # if there was albumart, delete the temp file
            try:
                subprocess.check_call('rm {}'.format(self.params['artwork']),
                                      shell=True)
            except KeyError:
                self.logger.debug('No artwork to delete')
            move_to_trash(self.file_name)
            command = 'mv {} "{}"'.format(tmp_file_name, self.file_name)
            subprocess.check_call(command, shell=True)
        except subprocess.CalledProcessError as e:
            error1 = 'An error occured while tagging {}.'
            error2 = 'AtomicParsley Error-Code: {}'
            error = ' '.join([error1, error2])
            error = error.format(self.file_name, e.returncode)
            self.logger.error(error)


class TVTagger(Tagger):
    """Tagger Subclass tailored to tagging TV Show metadata"""
    def __init__(self, file_name, customs=None, auto_tag=True):
        super(TVTagger, self).__init__()
        self.params = {'stik': 'TV Show', 'disk': '1/1', 'comment': '',
                       'apID': __email__}
        self.tvdb = Tvdb(actors=True)
        trakt_key = '888dbf16c37694fd8633f0f7e423dfc5'
        configure(trakt_key)
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name
        self.customs = customs or {}

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
                title_comparator = re.sub(r'\W+', ' ',
                                          self.params['TVShowName'])
                for res in season_results:
                    comparative_title = re.sub(r'\W+', ' ', res.artist.name)
                    if title_comparator.lower() == comparative_title.lower() \
                            and self.params[
                                'TVSeasonNum'] in res.get_album().name:
                        season_data = res
                        break
                # Copyright info
                parameters['copyright'] = season_data.get_copyright()
                url = season_data.get_artwork()
                url = string.replace(url['60'], '60x60-50', '600x600-75')
                if self.has_artwork(url):
                    pid = str(os.getpid())
                    parameters['artwork'] = '.albumart{}.jpg'.format(pid)
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
            parameters['genre'] = episode_data.get_genre()
            # Genre ID
            parameters['geID'] = TV_GENREIDS[parameters['genre']]
            # Release Date
            parameters['year'] = episode_data.get_release_date()
            # short description, max length 255 characters
            description = episode_data.get_short_description().strip()[:255]
            description = string.replace(description, '\n', '')
            parameters['description'] = strip_unicode(description)
            # long description
            parameters['longdesc'] = episode_data.get_long_description().strip()
            parameters['longdesc'] = string.replace(parameters['longdesc'],
                                                    '\n', '')
            # iTunes Catalog ID
            parameters['cnID'] = episode_data.get_episodeID()
            # Content Rating
            parameters['contentRating'] = episode_data.get_content_rating()
        return parameters

    def do_trakt_search(self):
        """Search Trakt.TV for data on the episode being tagged"""
        show_name = self.params['TVShowName']
        season_num = int(self.params['TVSeasonNum'])
        if int(self.params['TVEpisodeNum']) != 0:
            episode_num = int(self.params['TVEpisodeNum']) - 1
        else:
            int(self.params['TVEpisodeNum'])
        msg = '{} : {} : {}'.format(show_name, season_num, episode_num)
        self.logger.warning(msg)
        show = TVShow(show_name)
        self.logger.warning(pformat(show.search_season(season_num).__dict__))
        episode = show.search_season(season_num).episodes[episode_num]
        self.logger.warning(pformat(episode.__dict__))

        self.params['contentRating'] = show.certification
        self.params['genre'] = show.genres[0]
        self.params['TVNetwork'] = show.network
        actors = []
        for actor in show.people['actors']:
            if 'name' in actor:
                actors.append(actor['name'])
        
        self.params['year'] = episode.first_aired_iso
        self.params['description'] = self.params['longdesc'] = episode.overview
        if len(self.params['description']) > 250:
            self.params['description'] = self.params['description'][:250]
            count = 0
            for ch in self.params['description']:
                if ch == '"':
                    count += 1
            if count % 2 != 0:
                self.params['description'] += '"'
        self.params['TVShowName'] = self.params['artist'] = episode.show
        self.params['title'] = episode.title
        # Reformat fields
        self.params['albumArtist'] = episode.show
         # Reformat album name
        self.params['album'] = '{}, Season {}'.format(self.params['artist'],
                                                      self.params['TVSeasonNum'])
        if self.params['genre'] in TV_GENREIDS:
            self.params['geID'] = TV_GENREIDS[self.params['genre']]

    def collect_metadata(self, trakt=False):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        try:
            for key, val in self.customs.items():
                self.params[key] = val
        except Exception:
            pass
        vid = self.file_name
        extension = os.path.splitext(vid)[-1].lower()
        if extension not in self.supported_types:
            self.logger.err('Unsupported file type'.format(extension))
        else:
            # File name (Episode # Episode Name)
            basename = string.replace(os.path.basename(vid), '\\', '').strip()
            self.logger.info('Tagging {}'.format(basename))
            # folder containing file (Season #)
            sea_name = string.replace(os.path.dirname(vid), '\\', '')
            # folder containing folder (Show Name)
            sho_name = string.replace(os.path.dirname(sea_name), '\\', '')
            # episode number
            episode = basename[:2].strip()
            # name of episode
            self.params['title'] = basename[3:-4].strip()
            # season number
            self.params['TVSeasonNum'] = sea_name[-2:].strip()
            # name of show
            self.params['artist'] = self.params['albumArtist'] = \
                self.params['TVShowName'] = os.path.basename(sho_name)
            # format episode number
            try:
                if int(episode) < 10:
                    episode = episode[1:].encode('utf-8').strip()
                    self.params['TVEpisodeNum'] = self.params[
                        'tracknum'] = episode
                else:
                    self.params['TVEpisodeNum'] = self.params[
                        'tracknum'] = episode.encode('utf-8').strip()
            except ValueError:
                try:
                    # Check to see if episode is in format 'Episode #'
                    episode = basename.split(' ')
                    episode = episode[len(episode) - 1][:-4].strip()
                    self.params['title'] = basename[:-4].strip()
                    if int(episode) < 10:
                        self.params['TVEpisodeNum'] = self.params[
                            'tracknum'] = episode
                    else:
                        self.params['TVEpisodeNum'] = self.params[
                            'tracknum'] = episode.encode('utf-8').strip()
                except ValueError:
                    # No episode number could be found
                    pass
            # Format episode ID
            self.params['TVEpisode'] = 'S{}E{}'.format(
                self.params['TVSeasonNum'], self.params['TVEpisodeNum'])
            # Format album name
            self.params['album'] = '{}, Season {}'.format(self.params['artist'],
                                                          self.params[
                                                              'TVSeasonNum'])
            # Build queries for iTunes search
            tmp = dict()
            tmp['season'] = '{} {}'.format(self.params['artist'],
                                           self.params['TVSeasonNum'])
            query_title = self.params['title'].lower()
            query_title = (string.replace(query_title, '-', ' ')).strip()
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
            tmp['episode'] = '{} {}'.format(self.params['TVShowName'],
                                            query_title)
            # Concatenate parameters with iTunes query results
            self.params = dict_concat(self.params, self.do_itunes_search(tmp))
            self.do_tvdb_search()
            if self.params['artist'] == 'Archer (2009)':
                self.params['artist'] = 'Archer'
            if 'longdesc' not in self.params.keys() and 'description' in \
                    self.params.keys():
                self.params['longdesc'] = self.params['description']
            if trakt:
                self.do_trakt_search()
            self.do_tagging()


class MusicTagger(Tagger):
    """Tagger Subclass tailored to tagging Music metadata"""
    def __init__(self, file_name, auto_tag=True):
        super(MusicTagger, self).__init__()
        self.params = {'stik': 'Music', 'disk': '1/1', 'comment': '',
                       'apID': __email__}
        self.supported_types = ['.m4a']
        self.file_name = file_name

    def do_itunes_search(self, query):
        """This method uses the provided query for performing an iTunes audio
        track search
        """
        results = itunes.search_track(query)
        track = None
        for result in results:
            if self.params['title'] in result.get_name() and \
                            self.params['artist'] == result.get_artist().name:
                track = result
                break
        if track:
            # Album
            self.params['album'] = track.get_album()
            # Albumart
            url = track.artwork
            url = string.replace(albumArt['60'], '60x60-50', '600x600-75')
            if self.has_artwork(url):
                pid = str(os.getpid())
                parameters['artwork'] = '.albumart{}.jpg'.format(pid)
            # Genre
            self.params['genre'] = track.get_genre()
            album = track.get_album()
            self.params['copyright'] = album.copyright
            self.params['tracknum'] = '{}/{}'.format(self.params['tracknum'],
                                                     album.get_track_count())
            self.params['year'] = album.get_release_date_raw()
            self.params['albumArtist'] = self.params['artist']
            self.params['cnID'] = track.get_id()
            if track.json['trackExplicitness'].lower() == 'explicit':
                self.params['advisory'] = 'explicit'
            self.do_tagging()
        else:
            self.logger.err('{} not found in iTunes'.format(query))

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        song = self.file_name
        extension = os.path.splitext(song)[-1].lower()
        if extension not in self.supported_types:
            self.logger.err('{} given to be tagged, but {} is not a supported'
                            ' file type'.format(song, extension))
        else:
            #filename (Track # Track Name)
            basename = string.replace(os.path.basename(song), '\\', '').strip()
            #folder containing file (Album Name or Unknown Album)
            self.params['album'] = string.replace(os.path.dirname(song), '\\',
                                                  '')
            #folder containing folder (Artist Name)
            self.params['artist'] = string.replace(
                os.path.dirname(self.params['album']), '\\', '')
            self.params['album'] = os.path.basename(self.params['album'])
            self.params['artist'] = os.path.basename(self.params['artist'])
            #track number
            self.params['tracknum'] = basename[:2].strip()
            #name of Track
            self.params['title'] = basename[3:-4].strip()
            query = '{} {}'.format(self.params['artist'], self.params['title'])
            self.do_itunes_search(query)


class MovieTagger(Tagger):
    """Tagger Subclass tailored to tagging Movie metadata"""
    def __init__(self, file_name, auto_tag=True):
        super(MovieTagger, self).__init__()
        self.params = {'stik': 'Movie', 'disk': '1/1', 'comment': '',
                       'apID': __email__}
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name
        trakt_key = '888dbf16c37694fd8633f0f7e423dfc5'
        configure(trakt_key)

    def do_itunes_search(self):
        """This method pulls the title of the current Movie out of the
        parameters dictionary. This title is then used as the query for an
        iTunes movie search
        """
        self.logger.info('Performing iTunes Search')
        movie_results = itunes.search_movie(self.params['title'])
        table = string.maketrans('', '')
        movie_data = None
        for result in movie_results:
            result_name = result.get_name().lower()
            result_name = result_name.translate(table, string.punctuation)
            result_name = string.replace(result_name, '  ', ' ')
            title = self.params['title'].lower()
            title = title.translate(string.maketrans('', ''),
                                    string.punctuation)
            title = string.replace(title, '  ', ' ')
            if result_name == title:
                self.params['title'] = strip_unicode(result.get_name())
                movie_data = result
        if movie_data is None:
            for result in movie_results:
                if result.get_name().lower() == self.params['title'].lower():
                    self.params['title'] = strip_unicode(result.get_name())
                    movie_data = result
                    break
                else:
                    words = self.params['title'].lower().translate(
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
                parameters['artwork'] = '.albumart{}.jpg'.format(pid)
            json = movie_data.json
            # Content Rating
            self.params['contentRating'] = json['contentAdvisoryRating']
            # Explcitness
            self.params['advisory'] = json['trackExplicitness']
            if self.params['advisory'] == 'notExplicit':
                self.params['advisory'] = 'clean'
            # Description
            self.params['longdesc'] = strip_unicode(json['longDescription'])
            self.params['description'] = self.params['longdesc'][:250]
            if self.params['description'].count('"') % 2 != 0:
                self.params['description'] += '"'
            # Genre
            self.params['genre'] = json['primaryGenreName']
            # Release Date
            self.params['year'] = json['releaseDate']
            # Genre ID
            self.params['geID'] = MOVIE_GENREIDS[self.params['genre']]
            # Catalog ID
            self.params['cnID'] = movie_data.get_id()

    def do_trakt_search(self):
        """Search Trakt.TV for data on the movie being tagged"""
        title = self.params['title']
        year = None
        if '(' in title and ')' in title:
            year = title[title.find('(')+1:title.find(')')].strip()
            title = ' '.join(title.split()[:-1]).strip()
        movie = Movie(title, year=year)
        self.params['contentRating'] = movie.certification
        self.params['genre'] = movie.genres[0]
        self.params['description'] = self.params['longdesc'] = movie.overview
        self.params['year'] = movie.released_iso
        self.params['title'] = movie.title
        if 'artwork' not in self.params and 'poster' in movie.images:
            if self.has_artwork(movie.images['poster']):
                pid = str(os.getpid())
                self.params['artwork'] = '.albumart{}.jpg'.format(pid)

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        vid = self.file_name
        extension = os.path.splitext(vid)[-1].lower()
        if extension not in self.supported_types:
            self.logger.err('{} given to be tagged, but {} is not a '
                            'supported file type'.format(vid, extension))
        else:
            self.logger.info('Tagging {}'.format(os.path.basename(vid)))
            # Title
            self.params['title'] = string.replace(os.path.basename(vid),
                                                  '\\', '').strip()[:-4]
            self.do_itunes_search()
            self.do_trakt_search()
            self.do_tagging()
