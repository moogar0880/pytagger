import string
import sys
reload(sys)
sys.setdefaultencoding("utf8")
import os
import subprocess
import re
import logging
import time
from multiprocessing import Pool, cpu_count
from datetime import date
from optparse import OptionParser
from contextlib import contextmanager
try:
    import requests
except ImportError:
    print 'requests module not installed'
try:
    import itunes
except ImportError:
    print 'pyitunes not installed'
try:
    from tvdb_api import Tvdb
    import tvdb_api
except ImportError:
    print 'tvdb_api not installed'
try:
    import tmdb
except ImportError:
    print 'tmdb not installed'

__name__       = 'pytagger'
__doc__        = 'A python backend to iTunes style metadata tagging'
__author__     = 'Jonathan Nappi'
__version__    = '0.5.6'
__license__    = 'GPL'
__maintainer__ = 'Jonathan Nappi'
__email__      = 'moogar@comcast.net'
__status__     = 'Beta'
__title__      = "{} version {}".format(__name__, __version__)

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
                  'Tokusatsu': 4427, 'Korean Cinema': 4428 }

@contextmanager
def ignored(*exceptions):
    """
    Context manager to ignore specified exceptions and logging pertinent info

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
    """
    Move the provided file to it's closest Trash folder
    """
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
                subprocess.call('mv "{}" "{}"'.format(file_path, users_volume_trash), shell=True)
            else:
                os.mkdir(users_volume_trash)
                subprocess.call('mv "{}" "{}"'.format(file_path, users_volume_trash), shell=True)
        elif os.path.exists(local_trash):
            subprocess.call('mv "{}" "{}"'.format(file_path, local_trash), shell=True)
        else:
            print 'ERROR: Can not find Trash'
        subprocess.call('mv "{}" "{}"'.format(file_path, local_trash), shell=True)
    else:
        print 'No idea whats happening...'

def dict_concat(d1, d2):
    """
    Universal dicttionary concatinator.
    WARNING: Assumes that all key values will be unique
    """
    for key in d2.keys():
        d1[key] = d2[key]
    return d1

def get_xml_entry(name):
    """
    Get the XML formatted name
    """
    return '\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n'.format(name)

def create_iTunes_xml(cast, directors, producers, writers):
    """
    Function for generating the rDNSatom XML data required for iTunes style
    metadata to be able to list the actors, directors, producers, and writers
    for any video media type to be tagged
    """
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD\ PLIST\ 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
"""
    if cast != None and cast != []:
        xml += "\t<key>cast</key>\n\t<array>\n"
        for name in cast:
            if name != None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    if directors != None and directors != []:
        xml += "\t<key>directors</key>\n\t<array>\n"
        for name in directors:
            if name != None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    if producers != None and producers != []:
        xml += "\t<key>producers</key>\n\t<array>\n"
        for name in producers:
            if name != None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    if writers != None and writers != []:
        xml += "\t<key>screenwriters</key>\n\t<array>\n"
        for name in writers:
            if name != None and len(name) > 0:
                xml += get_xml_entry(name)
        xml += "\t</array>\n"

    xml += "</dict>\n</plist>"
    return xml

class Tagger(object):
    """
    Generic Tagger Class
    """
    def __init__(self):
        super(Tagger, self).__init__()
        self.logger = TaggingLogger()

    def has_artwork(self, url):
        """
        Attempts to download artwork from the provided URL and write it to a
        .jpg file named '.albumart.jpg' then return True as long as a valid HTTP
        response is recieved. If an error should occur, nothing is downloaded
        and False is returned
        """
        self.logger.info("Downloading Album Artwork...\n\tURL: {}".format(url))
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
            command = "AtomicParsley \"{}\" --artwork REMOVE_ALL --output \".tmp.m4v\"".format(filename)
        else:
            command = "AtomicParsley \"{}\" --output \".tmp.m4v\"".format(filename)
        keys = params.keys()
        for key in keys:
            if key == 'rDNSatom':
                command += " --" + key + " \"" + str(params[key]) + "\" name=iTunMOVI domain=com.apple.iTunes"
            else:
                command += " --" + key + " \"" + str(params[key]) + "\""
        #Need to prevent Non-zero exit status 2 AP erorrs from halting the entire program
        try:
            print 'Beginning Metadata tagging...'
            subprocess.check_call(command, shell=True)
            print 'Metadata tagging complete. moving updated file'
            #if there was albumart, delete the temp file
            try:
                subprocess.check_call("rm {}".format(params['artwork']), shell=True)
            except KeyError:
                print 'no artwork to delete'
            command = "mv \"{}\" \"{}\"-old".format(filename, filename)
            # command = "mv \"{}\" \"/Volumes/TV Shows/.Trashes/501/\"".format(filename)
            move_to_trash(filename)
            command = "mv .tmp.m4v \"{}\"".format(filename)
            subprocess.check_call(command, shell=True)
        except subprocess.CalledProcessError as e:
            print "An error occured while tagging {}. AtomicParsley Error-Code: {}".format(filename, e.returncode)

    def writeOut(self):
        """
        """
        for vid, params in self.queue:
            self.do_tagging(vid, params)

class TVTagger(Tagger):
    """
    Tagger Subclass tailored to tagging TV Show metadata
    """
    def __init__(self, files):
        super(TVTagger, self).__init__()
        self.params = {'stik': 'TV Show', 'disk': '1/1', 'comment': '', 'apID': __email__}
        self.tvdb = Tvdb(actors=True)
        self.supportedTypes = ['.mp4', '.m4v']
        self.fileCount   = len(files)
        self.fileCounter = 1
        self.files = files

    def do_iTunes_search(self, queries):
        """
        This method pulls the provided queries out of their list and then uses
        them as the queries for their respective iTunes searches
        """
        parameters = {}
        search = queries['season']
        self.logger.info("Searching iTunes for {}".format(search))
        #Gather Season information
        seasonResults = itunes.search_season(search)
        seasonData    = None
        with ignored(AttributeError):
            #Get season data from iTunes
            if seasonResults != []:
                titleComparator = re.sub(r'\W+', ' ', self.params['TVShowName'])
                for res in seasonResults:
                    comparativeTitle = re.sub(r'\W+', ' ', res.artist.name)
                    if titleComparator.lower() == comparativeTitle.lower() and self.params['TVSeasonNum'] in res.get_album().name:
                        seasonData = res
                        break
                #Copyright info
                parameters['copyright'] = seasonData.get_copyright()
                url = seasonData.get_artwork()
                url = string.replace(url['60'], '60x60-50', '600x600-75')
                if self.has_artwork(url):
                    parameters['artwork'] = '.albumart.jpg'
            if seasonData == None:
                self.logger.log('{} not found in iTunes'.format(search))

        #Gather episode information
        search = queries['episode']
        self.logger.info('Searching iTunes for {}'.format(search))
        episodeResults = itunes.search_episode(search)
        episodeData    = None
        else:
            if episodeResults != []:
                episodeData = episodeResults[0]
            else:
                self.logger.log('{} not found in iTunes'.format(search))
            with ignored(AttributeError):
                #Genre
                parameters['genre'] = episodeData.get_genre()
                #Genre ID
                parameters['geID']  = TV_GENREIDS[parameters['genre']]
                #Release Date
                parameters['year']  = episodeData.get_release_date()
                #short description, max length 255 characters
                parameters['description']   = episodeData.get_short_description().strip()[:255]
                parameters['description']   = string.replace(parameters['description'], "\n", "")
                #long description
                parameters['longdesc']      = episodeData.get_long_description().strip()
                parameters['longdesc']      = string.replace(parameters['longdesc'], "\n", "")
                #iTunes Catalog ID
                parameters['cnID']          = episodeData.get_episodeID()
                #Content Rating
                parameters['contentRating'] = episodeData.get_content_rating()
        return parameters

    def do_TVDB_search(self):
        """
        By pulling in relevant pre-recieved metadata fields perform a search on
        the TVDB for season and episode metadata
        """
        #TVDB query for cast, writers, director
        querySeason  = int(self.params['TVSeasonNum'])
        queryEpisode = int(self.params['TVEpisodeNum'])
        actors = []
        directors = writers = ''
        if self.params['artist'] == 'Archer':
            self.params['artist'] = 'Archer (2009)'
        with ignored(Exception):
            show = self.tvdb[self.params['artist']]
            for actor in show['_actors']:
                actors.append(actor['name'])
            episode = show[querySeason][queryEpisode]
            #iTunes descriptions can be terrible, use TVDB's when available
            self.params['description'] = episode['overview'].strip()[:255]
            self.params['description'] = string.replace(self.params['description'], "\"", "\\\"")
            self.params['description'] = string.replace(self.params['description'], "\n", "")
            #Different quote character can create AP non-zero exit status 2 problems
            #If longdesc from TVDB is longer than iTunes, use that instead
            if len(self.params['description']) > len(self.params['longdesc']):
                self.params['longdesc'] = self.params['description']
            directors = episode['director']
            #parse out director names
            if directors != None:
                directors = directors.split('|')
            writers   = episode['writer']
            #parse out writer names
            if writers != None:
                writers   = writers.split('|')
            self.params['rDNSatom'] = create_iTunes_xml(actors, directors, [], writers)
            newReleaseDate = episode['firstaired']
            if newReleaseDate != "":
                self.params['year'] = newReleaseDate + 'T00:00:00Z'

    def collect_metadata(self):
        """
        Checks that each file passed in is of a valid type. Providing that the
        file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        if len(self.files) == 0:
            self.logger.err("No files give to tag")
            os._exit(os.EX_OK)
        i = 1
        for vid in self.files:
            extension = os.path.splitext(vid)[-1].lower()
            if extension not in self.supportedTypes:
                self.logger.err("{} given to be tagged, but {} is not a supported file type".format(vid,extension))
            else:
                #filename (Episode # Episode Name)
                basename = string.replace(os.path.basename(vid), "\\", "").strip()
                self.logger.info("Tagging {}".format(basename))
                #folder containing file (Season #)
                seaName  = string.replace(os.path.dirname(vid), "\\", "")
                #folder containing folder (Show Name)
                shoName  = string.replace(os.path.dirname(seaName), "\\", "")
                #episode number
                episode  = basename[:2].strip()
                #name of episode
                self.params['title'] = basename[3:-4].strip()
                #season number
                self.params['TVSeasonNum'] = seaName[-2:].strip()
                #name of show
                self.params['artist']      = os.path.basename(shoName)
                self.params['albumArtist'] = os.path.basename(shoName)
                self.params['TVShowName']  = os.path.basename(shoName)
                #format episode number
                try:
                    if int(episode) < 10:
                        episode = episode[1:].encode('utf-8').strip()
                        self.params['TVEpisodeNum'] = self.params['tracknum'] = episode
                    else:
                        self.params['TVEpisodeNum'] = self.params['tracknum'] = episode.encode('utf-8').strip()
                except ValueError:
                    try: #Check to see if episode is in format 'Episode #'
                        episode = basename.split(' ')
                        episode = episode[len(episode)-1][:-4].strip()
                        self.params['title'] = basename[:-4].strip()
                        if int(episode) < 10:
                            self.params['TVEpisodeNum'] = self.params['tracknum'] = episode
                        else:
                            self.params['TVEpisodeNum'] = self.params['tracknum'] = episode.encode('utf-8').strip()
                    except ValueError:
                        episode = str(i)
                        self.params['title'] = basename[:-4].strip()
                        if int(episode) < 10:
                            self.params['TVEpisodeNum'] = self.params['tracknum'] = episode
                        else:
                            self.params['TVEpisodeNum'] = self.params['tracknum'] = episode.encode('utf-8').strip()

                #format episode ID
                self.params['TVEpisode'] = "S{}E{}".format(self.params['TVSeasonNum'], self.params['TVEpisodeNum'])
                #format album name
                self.params['album'] = "{}, Season {}".format(self.params['artist'], self.params['TVSeasonNum'])
                #setup and perform iTunes query
                iTunesQuery          = "{} {}".format(self.params['artist'], self.params['TVSeasonNum'])
                #Build queries for iTunes search
                tmp = {}
                tmp['season']  = "{} {}".format(self.params['artist'], self.params['TVSeasonNum'])
                queryTitle = self.params['title'].lower()
                #queryTitle = (string.replace(title.lower(), "the ", "")).strip()
                queryTitle = (string.replace(queryTitle, "-", " ")).strip()
                if 'part ' in queryTitle:
                    queryTitle = string.replace(queryTitle, "part ", "pt ")
                if 'pt i' in queryTitle:
                    queryTitle = string.replace(queryTitle, "pt i", "pt 1")
                if 'pt ii' in queryTitle:
                    queryTitle = string.replace(queryTitle, "pt ii", "pt 2")
                if 'pt iii' in queryTitle:
                    queryTitle = string.replace(queryTitle, "pt iii", "pt 3")
                if 'fuckers' in queryTitle:
                    queryTitle = string.replace(queryTitle, "fuckers", "fu*kers")
                if 'fucker' in queryTitle:
                    queryTitle = string.replace(queryTitle, "fucker", "f*****")
                if 'fuck' in queryTitle:
                    queryTitle = string.replace(queryTitle, "fuck", "f***")
                tmp['episode'] = "{} {}".format(self.params['TVShowName'], queryTitle)
                #Concatinate parameters with iTunes query results
                self.params  = dict_concat(self.params, self.do_iTunes_search(tmp))
                self.do_TVDB_search()
                if self.params['artist'] == 'Archer (2009)':
                    self.params['artist'] = 'Archer'
                if 'longdesc' not in self.params.keys() and 'description' in self.params.keys():
                    self.params['longdesc'] = self.params['description']

                self.do_tagging(vid, self.params)
            print "{0:.2f}% done".format(100.0*(float(self.fileCounter)/float(self.fileCount)))
            self.fileCounter += 1
            i = i + 1

class MusicTagger(Tagger):
    """
    Tagger Subclass tailored to tagging Music metadata
    """
    def __init__(self, files):
        super(MusicTagger, self).__init__()
        self.params = {'stik': 'Music', 'disk': '1/1', 'comment': '', 'apID': __email__, 'output': 'tmp.m4a'}
        self.supportedTypes = ['.m4a']
        self.fileCount   = len(files)
        self.fileCounter = 1
        self.files = files

    def do_iTunes_search(self, query):
        """
        This method uses the provided query for performing an iTunes audio
        track search
        """
        results = itunes.search_track(query)
        track   = None
        for result in results:
            if self.params['title'] in result.get_name() and self.params['artist'] == result.get_artist().name:
                track = result
                break
        if track:
            #Album
            self.params['album'] = track.get_album()
            #Albumart
            url  = track.artwork
            url  = string.replace(albumArt['60'], "60x60-50", "600x600-75")
            if self.has_artwork(url):
                self.params['artwork'] = '.albumart.jpg'
            #Genre
            self.params['genre'] = track.get_genre()
            album = track.get_album()
            self.params['copyright']   = album.copyright
            self.params['tracknum']    = "{}/{}".format(self.params['tracknum'], album.get_track_count())
            self.params['year']        = album.get_release_date_raw()
            self.params['albumArtist'] = self.params['artist']
            self.params['cnID']        = track.get_id()
            if track.json['trackExplicitness'].lower() == 'explicit':
                self.params['advisory'] = 'explicit'
            self.do_tagging(song, self.params)
        else:
            self.logger.err("{} not found in iTunes".format(query))

    def collect_metadata(self, custom_args):
        """
        Checks that each file passed in is of a valid type. Providing that the
        file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        if len(self.files) == 0:
            self.logger.err("No files give to tag")
            os._exit(os.EX_OK)
        for song in self.files:
            #need to check filetype
            extension = os.path.splitext(song)[-1].lower()
            if extension not in self.supportedTypes:
                self.logger.err("{} given to be tagged, but {} is not a supported file type".format(song,extension))
            else:
                #filename (Track # Track Name)
                basename = string.replace(os.path.basename(song), "\\", "").strip()
                #folder containing file (Album Name or Unknown Album)
                self.params['album']    = string.replace(os.path.dirname(song), "\\", "")
                #folder containing folder (Artist Name)
                self.params['artist']   = string.replace(os.path.dirname(self.params['album']), "\\", "")
                self.params['album']    = os.path.basename(self.params['album'])
                self.params['artist']   = os.path.basename(self.params['artist'])
                #track number
                self.params['tracknum'] = basename[:2].strip()
                #name of Track
                self.params['title']    = basename[3:-4].strip()
                query = "{} {}".format(self.params['artist'], self.params['title'])
                self.do_iTunes_search(query)

class MovieTagger(Tagger):
    """
    Tagger Subclass tailored to tagging Movie metadata
    """
    def __init__(self, files):
        super(MovieTagger, self).__init__()
        self.params = {'stik': 'Movie', 'disk': '1/1', 'comment': '',
                       'apID': __email__, 'output': '.tmp.m4v'}
        self.supportedTypes = ['.mp4', '.m4v']
        self.files = files
        self.queue = []

    def do_iTunes_search(self):
        """
        This method pulls the title of the current Movie out of the parameters
        dictionary. This title is then used as the query for an iTunes movie
        search
        """
        movieResults = itunes.search_movie(self.params['title'])
        for result in movieResults:
            if result.get_name().lower() == self.params['title'].lower():
                movieData = result
                break
            else:
                words = self.params['title'].lower().translate(string.maketrans("",""), string.punctuation).split(' ')
                total = len(words)
                matches = 0
                result_words = result.get_name().lower().translate(string.maketrans("",""), string.punctuation).split(' ')
                for word in words:
                    if word in result_words:
                        matches += 1
                if float(matches)/float(total) > 0.8:
                    movieData = result
                    break
        with ignored(Exception):
            #Artwork
            url = movieData.get_artwork()
            url = string.replace(url['60'], "60x60-50", "600x600-75")
            if self.has_artwork(url):
                self.params['artwork'] = '.albumart.jpg'
            json = movieData.json
            #Content Rating
            self.params['contentRating'] = json['contentAdvisoryRating']
            #Explcitness
            self.params['advisory'] = json['trackExplicitness']
            if self.params['advisory'] == 'notExplicit':
                self.params['advisory'] = 'clean'
            #Description
            self.params['longdesc'] = json['longDescription']
            self.params['description'] = self.params['longdesc'][:253]
            #Genre
            self.params['genre'] = json['primaryGenreName']
            #Release Date
            self.params['year'] = json['releaseDate']
            #Genre ID
            self.params['geID']  = MOVIE_GENREIDS[self.params['genre']]
            #Catalog ID
            self.params['cnID']  = movieData.get_id()

    def do_TMDB_search(self):
        """
        This method pulls the title of the current Movie out of the parameters
        dictionary. This title is then used as the query for a TMDB movies
        search
        """
        #Insert TMDB API key here
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
        if movie != None:
            #Release Date
            self.params['year']        = movie.get_release_date()
            #Short Description
            self.params['description'] = movie.get_overview()[:253]
            #Long Description
            self.params['longdesc']    = movie.get_overview()
            #If iTunes data was not found, fill in the fields from the iTunes search
            if 'genre' not in self.params.keys() and movie.get_genres() != []:
                self.params['genre'] = movie.get_genres()[0]['name']
            if 'artwork' not in self.params.keys():
                if self.has_artwork(movie.get_poster()):
                    self.params['artwork'] = '.albumart.jpg'
            #Need to do some fancy querying to get movie's cast
            credits = movie.getJSON(tmdb.config['urls']['movie.casts'] % movie.get_id(), 'en')
            #Actors
            actors = []
            for actor in credits['cast']:
                actors.append(actor['name'])
            #Directors, Writers, Producers
            directors = producers = writers = []
            for member in credits['crew']:
                if member['job'].lower() == 'director' and member['name'] not in directors:
                    directors.append(member['name'])
                elif member['job'].lower() == 'writer' and member['name'] not in writers:
                    writers.append(member['name'])
                elif member['job'].lower == 'producer' and member['name'] not in producers:
                    producers.append(member['name'])
            self.params['rDNSatom'] = create_iTunes_xml(actors, directors, producers, writers)

    def collect_metadata(self):
        """
        Checks that each file passed in is of a valid type. Providing that the
        file was of the correct type, the various searches are performed and
        all metadata is gathered.
        """
        if( len(self.files) == 0 ):
            self.logger.err("No files give to tag")
            os._exit(os.EX_OK)
        for vid in self.files:
            #need to check filetype
            extension = os.path.splitext(vid)[-1].lower()
            if extension not in self.supportedTypes:
                self.logger.err("{} given to be tagged, but {} is not a supported file type".format(vid,extension))
            else:
                self.logger.info("Tagging {}".format(os.path.basename(vid)))
                #title
                self.params['title'] = string.replace(os.path.basename(vid), "\\", "").strip()[:-4]
                # self.params['title'] = string.replace(self.params['title'], " and ", " & ")
                # self.params['title'] = string.replace(self.params['title'], " - ", ": ")
                print self.params['title']

                self.do_iTunes_search()
                self.do_TMDB_search()
                # self.queue.append((vid, self.params))
                self.do_tagging(vid, self.params)

class TaggingLogger(object):
    """
    Logger wrapper class for PyTagger Logging
    """
    def __init__(self,name=None):
        super(TaggingLogger, self).__init__()
        logDate = date.today().isoformat()
        home = os.path.expanduser('~')
        if name == None:
            name = os.path.join(home, '.pytagger_logs/{}{}.log'.format(__name__, logDate))
        if not os.path.exists(os.path.join(home, '.pytagger_logs')):
            os.mkdir(os.path.join(home, '.pytagger_logs'))
        logging.basicConfig(filename=name, level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s:%(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S %p')
        self.name = name
        self.logger = logging.getLogger(__name__)
        self.start()

    def start(self):
        """
        Being a new logging session in the log file
        """
        f = open(self.name,'a')
        for i in range(15):
            f.write('=')
        f.write(self.name[5:-4])
        for i in range(15):
            f.write('=')
        f.write('\n\n')
        f.close()

    def finish(self):
        """
        Finish up the
        """
        f = open(self.name,'a')
        f.write('\n\n')
        f.close()

    def log(self,message):
        """
        Write a log message to the log file
        """
        self.logger.debug(message)

    def warn(self,message):
        """
        Write a warning log message to the log file
        """
        self.logger.warning(message)

    def info(self,message):
        """
        Write an info log message to the log file
        """
        self.logger.info(message)

    def err(self,message):
        """
        Write an error log message to the log file
        """
        self.logger.error(message)

    def crit(self,message):
        """
        Write a critical log message to the log file
        """
        self.logger.critical(message)
