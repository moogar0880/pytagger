import string
import sys
reload(sys)
sys.setdefaultencoding('utf8')
import os
import subprocess
import re
import logging
from datetime import date
from contextlib import contextmanager
import requests
import itunes
from tvdb_api import Tvdb
import tvdb_api
import tmdb

__name__       = 'pytagger'
__doc__        = 'A python backend to iTunes style metadata tagging'
__author__     = 'Jonathan Nappi'
__version__    = '0.6'
__license__    = 'GPL'
__maintainer__ = 'Jonathan Nappi'
__email__      = 'moogar@comcast.net'
__status__     = 'Beta'
__title__      = '{} version {}'.format(__name__, __version__)

#for TV shows only, movies have their own IDs
TV_GENREIDS = {'Comedy': 4000, 'Drama': 4001, 'Animation': 4002,
               'Action & Adventure': 4003, 'Classic': 4004, 'Kids': 4005,
               'Nonfiction': 4006, 'Reality TV': 4007,
               'Sci-Fi & Fantasy': 4008, 'Sports': 4009, 'Teens': 4010,
               'Latino TV': 4011 }

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
            print 'command: ', command
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
    else:
        pass


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


def create_iTunes_xml(cast, directors, producers, writers):
    """Function for generating the rDNSatom XML data required for iTunes style
    metadata to be able to list the actors, directors, producers, and writers
    for any video media type to be tagged
    """
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD\ PLIST\ 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
"""
    if cast is not None and cast != []:
        xml += "\t<key>cast</key>\n\t<array>\n"
        for name in cast:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    if directors is not None and directors != []:
        xml += "\t<key>directors</key>\n\t<array>\n"
        for name in directors:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    if producers is not None and producers != []:
        xml += "\t<key>producers</key>\n\t<array>\n"
        for name in producers:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    if writers is not None and writers != []:
        xml += "\t<key>screenwriters</key>\n\t<array>\n"
        for name in writers:
            if name is not None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    xml += "</dict>\n</plist>"
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
        logging.basicConfig(filename=name, level=logging.INFO,
                            format='%(asctime)s %(levelname)s:%(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S %p')
        self.logger = logging.getLogger(__name__)

    def has_artwork(self, url):
        """Attempts to download artwork from the provided URL and write it to a
        .jpg file named '.albumart.jpg' then return True as long as a 2xx HTTP
        response is recieved. If an error should occur, nothing is downloaded
        and False is returned
        """
        self.logger.info('Downloading Album Artwork...\n\tURL: {}'.format(url))
        req = requests.get(url)
        if req.status_code >= 200 and req.status_code < 300:
            f = open('.albumart.jpg','w')
            f.write(req.content)
            f.close()
            return True
        else:
            self.logger.log('Album Art Not Downloaded: {}'.format(req.status_code))
            return False

    def do_tagging(self, filename, params):
        """
        Builds the actual AtomicParsley call for the provided file and then
        makes the call to Atomic Parsley to actually write the metadata to the
        file.
        """
        if 'artwork' in params.keys():
            command = 'AtomicParsley "{}" --artwork REMOVE_ALL --output ".tmp.m4v"'.format(filename)
        else:
            command = 'AtomicParsley "{}" --output ".tmp.m4v"'.format(filename)
        keys = params.keys()
        for key in keys:
            if key == 'rDNSatom':
                command += ' --' + key + ' "' + str(params[key]) + \
                           '" name=iTunMOVI domain=com.apple.iTunes'
            else:
                command += ' --' + key + ' "' + str(params[key]) + '\"'
        # Need to prevent Non-zero exit status 2 AP errors from halting the 
        # entire program
        try:
            print 'Beginning Metadata tagging...'
            subprocess.check_call(command, shell=True)
            print 'Metadata tagging complete. moving updated file'
            # if there was albumart, delete the temp file
            try:
                subprocess.check_call('rm {}'.format(params['artwork']), 
                                      shell=True)
            except KeyError:
                print 'no artwork to delete'
            move_to_trash(filename)
            command = 'mv .tmp.m4v "{}"'.format(filename)
            subprocess.check_call(command, shell=True)
        except subprocess.CalledProcessError as e:
            print 'An error occured while tagging {}. AtomicParsley Error-Code: {}'.format(filename, e.returncode)


class TVTagger(Tagger):
    """Tagger Subclass tailored to tagging TV Show metadata"""
    def __init__(self, file_name, customs={}):
        super(TVTagger, self).__init__()
        self.params = {'stik': 'TV Show', 'disk': '1/1', 'comment': '',
                       'apID': __email__}
        self.tvdb = Tvdb(actors=True)
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name
        self.customs = customs

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
            if season_results != []:
                title_comparator = re.sub(r'\W+', ' ',
                                          self.params['TVShowName'])
                for res in season_results:
                    comparative_title = re.sub(r'\W+', ' ', res.artist.name)
                    if title_comparator.lower() == comparative_title.lower() \
                        and self.params['TVSeasonNum'] in res.get_album().name:
                        season_data = res
                        break
                # Copyright info
                parameters['copyright'] = season_data.get_copyright()
                url = season_data.get_artwork()
                url = string.replace(url['60'], '60x60-50', '600x600-75')
                if self.has_artwork(url):
                    parameters['artwork'] = '.albumart.jpg'
            if season_data is None:
                self.logger.log('{} not found in iTunes'.format(search))

        #Gather episode information
        search = queries['episode']
        self.logger.info('Searching iTunes for {}'.format(search))
        episode_results = itunes.search_episode(search)
        episode_data = None
        if episode_results != []:
            episode_data = episode_results[0]
        else:
            self.logger.log('{} not found in iTunes'.format(search))
        with ignored(AttributeError):
            # Genre
            parameters['genre'] = episode_data.get_genre()
            # Genre ID
            parameters['geID'] = TV_GENREIDS[parameters['genre']]
            # Release Date
            parameters['year'] = episode_data.get_release_date()
            # short description, max length 255 characters
            parameters['description'] = episode_data.get_short_description().strip()[:255]
            parameters['description'] = string.replace(parameters['description'], '\n', '')
            # long description
            parameters['longdesc'] = episode_data.get_long_description().strip()
            parameters['longdesc'] = string.replace(parameters['longdesc'], '\n', '')
            # iTunes Catalog ID
            parameters['cnID'] = episode_data.get_episodeID()
            # Content Rating
            parameters['contentRating'] = episode_data.get_content_rating()
        return parameters

    def do_tvdb_search(self):
        """By pulling in relevant pre-recieved metadata fields perform a search
        on the TVDB for season and episode metadata
        """
        # TVDB query for cast, writers, director
        query_season = int(self.params['TVSeasonNum'])
        query_episode = int(self.params['TVEpisodeNum'])
        actors = []
        directors = writers = ''
        if self.params['artist'] == 'Archer':
            self.params['artist'] = 'Archer (2009)'
        with ignored(Exception):
            show = self.tvdb[self.params['artist']]
            for actor in show['_actors']:
                actors.append(actor['name'])
            episode = show[query_season][query_episode]
            # iTunes descriptions can be terrible, use TVDB's when available
            self.params['description'] = episode['overview'].strip()[:255]
            self.params['description'] = string.replace(self.params['description'], '"', '\"')
            self.params['description'] = string.replace(self.params['description'], '\n', '')
            # Different quote character can create AP non-zero exit status 2
            # problems
            # If longdesc from TVDB is longer than iTunes, use that instead
            if len(self.params['description']) > len(self.params['longdesc']):
                self.params['longdesc'] = self.params['description']
            directors = episode['director']
            # parse out director names
            if directors is not None:
                directors = directors.split('|')
            writers = episode['writer']
            # parse out writer names
            if writers is not None:
                writers = writers.split('|')
            self.params['rDNSatom'] = create_iTunes_xml(actors, directors, [],
                                                        writers)
            new_release_date = episode['firstaired']
            if new_release_date != '':
                self.params['year'] = new_release_date + 'T00:00:00Z'

    def collect_metadata(self):
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
            self.logger.info("Tagging {}".format(basename))
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
                    self.params['TVEpisodeNum'] = self.params['tracknum'] = episode
                else:
                    self.params['TVEpisodeNum'] = self.params['tracknum'] = episode.encode('utf-8').strip()
            except ValueError:
                try:
                    # Check to see if episode is in format 'Episode #'
                    episode = basename.split(' ')
                    episode = episode[len(episode)-1][:-4].strip()
                    self.params['title'] = basename[:-4].strip()
                    if int(episode) < 10:
                        self.params['TVEpisodeNum'] = self.params['tracknum'] = episode
                    else:
                        self.params['TVEpisodeNum'] = self.params['tracknum'] = episode.encode('utf-8').strip()
                except ValueError:
                    # No episode number could be found
                    pass
            # Format episode ID
            self.params['TVEpisode'] = 'S{}E{}'.format(self.params['TVSeasonNum'], self.params['TVEpisodeNum'])
            # Format album name
            self.params['album'] = '{}, Season {}'.format(self.params['artist'], self.params['TVSeasonNum'])
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
            if 'longdesc' not in self.params.keys() and 'description' in self.params.keys():
                self.params['longdesc'] = self.params['description']
            self.do_tagging(vid, self.params)


class MusicTagger(Tagger):
    """Tagger Subclass tailored to tagging Music metadata"""
    def __init__(self, file_name):
        super(MusicTagger, self).__init__()
        self.params = {'stik': 'Music', 'disk': '1/1', 'comment': '',
                       'apID': __email__, 'output': 'tmp.m4a'}
        self.supported_types = ['.m4a']
        self.file_name = file_name

    def do_itunes_search(self, query):
        """This method uses the provided query for performing an iTunes audio
        track search
        """
        results = itunes.search_track(query)
        track = None
        for result in results:
            if self.params['title'] in result.get_name() and self.params['artist'] == result.get_artist().name:
                track = result
                break
        if track:
            # Album
            self.params['album'] = track.get_album()
            # Albumart
            url = track.artwork
            url = string.replace(albumArt['60'], '60x60-50', '600x600-75')
            if self.has_artwork(url):
                self.params['artwork'] = '.albumart.jpg'
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
            self.do_tagging(song, self.params)
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
            self.logger.err('{} given to be tagged, but {} is not a supported file type'.format(song, extension))
        else:
            #filename (Track # Track Name)
            basename = string.replace(os.path.basename(song), '\\', '').strip()
            #folder containing file (Album Name or Unknown Album)
            self.params['album'] = string.replace(os.path.dirname(song), '\\',
                                                  '')
            #folder containing folder (Artist Name)
            self.params['artist'] = string.replace(os.path.dirname(self.params['album']), '\\', '')
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
    def __init__(self, file_name):
        super(MovieTagger, self).__init__()
        self.params = {'stik': 'Movie', 'disk': '1/1', 'comment': '',
                       'apID': __email__, 'output': '.tmp.m4v'}
        self.supported_types = ['.mp4', '.m4v']
        self.file_name = file_name

    def do_itunes_search(self):
        """This method pulls the title of the current Movie out of the
        parameters dictionary. This title is then used as the query for an
        iTunes movie search
        """
        movie_results = itunes.search_movie(self.params['title'])
        movie_data = None
        for result in movie_results:
            if result.get_name.lower() == self.params['title'].lower():
                movie_data = result
        if movie_data is None:
            for result in movie_results:
                if result.get_name().lower() == self.params['title'].lower():
                    movie_data = result
                    break
                else:
                    words = self.params['title'].lower().translate(string.maketrans('', ''), string.punctuation).split(' ')
                    total = len(words)
                    matches = 0
                    result_words = result.get_name().lower().translate(string.maketrans('', ''), string.punctuation).split(' ')
                    for word in words:
                        if word in result_words:
                            matches += 1
                    if float(matches)/float(total) > 0.8:
                        movie_data = result
                        break
        with ignored(Exception):
            # Artwork
            url = movie_data.get_artwork()
            url = string.replace(url['60'], '60x60-50', '600x600-75')
            if self.has_artwork(url):
                self.params['artwork'] = '.albumart.jpg'
            json = movie_data.json
            # Content Rating
            self.params['contentRating'] = json['contentAdvisoryRating']
            # Explcitness
            self.params['advisory'] = json['trackExplicitness']
            if self.params['advisory'] == 'notExplicit':
                self.params['advisory'] = 'clean'
            # Description
            self.params['longdesc'] = json['longDescription']
            self.params['description'] = self.params['longdesc'][:253]
            # Genre
            self.params['genre'] = json['primaryGenreName']
            # Release Date
            self.params['year'] = json['releaseDate']
            # Genre ID
            self.params['geID'] = MOVIE_GENREIDS[self.params['genre']]
            # Catalog ID
            self.params['cnID'] = movie_data.get_id()

    def do_tmdb_search(self):
        """This method pulls the title of the current Movie out of the
        parameters dictionary. This title is then used as the query for a TMDB
        movies search
        """
        # Insert TMDB API key here
        api_key = '7b4534c44a0601d017210529c4cb2e5c'
        tmdb.configure(api_key)
        try:
            results = tmdb.Movies(self.params['title'])
        except KeyError as e:
            self.logger.err('TMDB Error {} Caught. Cancelling TMDB Search.'.format(e))
            return None
        movie = None
        for result in results.iter_results():
            if result['title'].lower() == self.params['title'].lower():
                movie = tmdb.Movie(result['id'])
                break
        if movie is not None:
            # Release Date
            self.params['year'] = movie.get_release_date()
            # Short Description
            self.params['description'] = movie.get_overview()[:253]
            # Long Description
            self.params['longdesc'] = movie.get_overview()
            # If iTunes data was not found, fill in the fields from the iTunes
            # search
            if 'genre' not in self.params.keys() and movie.get_genres() != []:
                self.params['genre'] = movie.get_genres()[0]['name']
            if self.has_artwork(movie.get_poster()):
                self.params['artwork'] = '.albumart.jpg'
            # Need to do some fancy querying to get movie's cast
            credits = movie.getJSON(tmdb.config['urls']['movie.casts'] % movie.get_id(), 'en')
            # Actors
            actors = []
            for actor in credits['cast']:
                actors.append(actor['name'])
            # Directors, Writers, Producers
            directors = producers = writers = []
            for member in credits['crew']:
                if member['job'].lower() == 'director' and member['name'] not in directors:
                    directors.append(member['name'])
                elif member['job'].lower() == 'writer' and member['name'] not in writers:
                    writers.append(member['name'])
                elif member['job'].lower == 'producer' and member['name'] not in producers:
                    producers.append(member['name'])
            self.params['rDNSatom'] = create_iTunes_xml(actors, directors,
                                                        producers, writers)

    def collect_metadata(self):
        """Checks that each file passed in is of a valid type. Providing that
        the file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        vid = self.file_name
        extension = os.path.splitext(vid)[-1].lower()
        if extension not in self.supported_types:
            self.logger.err('{} given to be tagged, but {} is not a supported file type'.format(vid, extension))
        else:
            self.logger.info('Tagging {}'.format(os.path.basename(vid)))
            # Title
            self.params['title'] = string.replace(os.path.basename(vid),
                                                  '\\', '').strip()[:-4]
            print self.params['title']
            self.do_itunes_search()
            self.do_tmdb_search()
            self.do_tagging(vid, self.params)
