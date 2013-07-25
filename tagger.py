import string
import sys
reload(sys)
sys.setdefaultencoding("utf8")
import os
import subprocess
import re
from optparse import OptionParser
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
__version__    = '0.2'
__license__    = 'GPL'
__maintainer__ = 'Jonathan Nappi'
__email__      = 'moogar@comcast.net'
__status__     = 'Alpha'
__title__      = "{} version {}".format(__name__, __version__)

#for TV shows only, movies have their own IDs
genreIDs = {'Comedy': 4000, 'Drama': 4001, 'Animation': 4002, 'Action & Adventure': 4003,
            'Classic': 4004, 'Kids': 4005, 'Nonfiction': 4006, 'Reality TV': 4007,
            'Sci-Fi & Fantasy': 4008, 'Sports': 4009, 'Teens': 4010, 'Latino TV': 4011 }

def main(argv=None):
    if argv is None:
        mediaType = parseOptions()
        argv = sys.argv[2:]
    if mediaType.show:
        tagger = TVTagger(argv)
    elif mediaType.movie:
        tagger = MovieTagger(argv)
    elif mediaType.music:
        tagger = MusicTagger(argv)

'''
Command line options parser
'''
def parseOptions():
    usage = "usage: tagger.py [options] [filenames]"
    parser = OptionParser(usage)
    parser.add_option("-t", "--TV",
                  action="store_true", dest="show",
                  help="declare media type as TV")
    parser.add_option("-m", "--Movie",
                  action="store_true", dest="movie",
                  help="declare media type as Movie")
    parser.add_option("-M", "--Music",
                  action="store_true", dest="music",
                  help="declare media type as Music")
    (options, args) = parser.parse_args()
    print options
    return options
    if options.show:
        tagger = TVTagger(argv)
    elif options.music:
        tagger = MusicTagger(argv)
    else:
        tagger = MovieTagger(argv)

'''
Universal dicttionary concatinator.
WARNING: Assumes that all key values will be unique
'''
def dictConcat(d1,d2):
    for key in d2.keys():
        d1[key] = d2[key]
    return d1

'''
Function for generating the rDNSatom XML data required for
iTunes style metadata to be able to list the actors, directors,
producers, and writers for any video media type to be tagged
'''
def createITunesXML(cast, directors, producers, writers):
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD\ PLIST\ 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
'''
    if cast != None and cast != []:
        xml += "\t<key>cast</key>\n\t<array>\n"
        for name in cast:
            if name != None and len(name) > 0:
                xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    if directors != None and directors != []:
        xml += "\t<key>directors</key>\n\t<array>\n"
        for name in directors:
            if name != None and len(name) > 0:
                xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    if producers != None and producers != []:
        xml += "\t<key>producers</key>\n\t<array>\n"
        for name in producers:
            if name != None and len(name) > 0:
                xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    if writers != None and writers != []:
        xml += "\t<key>screenwriters</key>\n\t<array>\n"
        for name in writers:
            if name != None and len(name) > 0:
                xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    xml += "</dict>\n</plist>"
    return xml

class Tagger():
    '''Generic Tagger Class'''
    def __init__(self):
        self.supportedTypes = ['.mp4', '.m4v']

    #Build Atomic Parsley Call
    def doTagging(self, filename, params):
        if 'artwork' in params.keys():
            command = "AtomicParsley \"{}\" --artwork REMOVE_ALL --output \"tmp.m4v\"".format(filename)
        else:
            command = "AtomicParsley \"{}\" --output \"tmp.m4v\"".format(filename)
        keys = params.keys()
        for key in keys:
            if key == 'rDNSatom':
                command += " --" + key + " \"" + str(params[key]) + "\" name=iTunMOVI domain=com.apple.iTunes"
            else:
                command += " --" + key + " \"" + str(params[key]) + "\""
        #print command
        #Need to prevent Non-zero exit status 2 AP erorrs from halting the entire program
        try:
            print "Beginning Metadata tagging..."
            subprocess.check_call(command, shell=True)
            print "Metadata tagging complete. moving updated file"
            #if there was albumart, delete the temp file
            try:
                subprocess.check_call("rm {}".format(params['artwork']), shell=True)
            except KeyError:
                print "no artwork to delete"
            command = "mv \"{}\" \"{}\"-old".format(filename, filename)
            command = "mv \"{}\" \"/Volumes/TV Shows/.Trashes/501/\"".format(filename)
            #print command
            subprocess.check_call(command, shell=True)
            command = "mv tmp.m4v \"{}\"".format(filename)
            #print command
            subprocess.check_call(command, shell=True)
        except subprocess.CalledProcessError as e:
            print "An error occured while tagging {}. AtomicParsley Error-Code: {}".format(filename, e.returncode)

class TVTagger(Tagger):
    '''Tagger Subclass tailored to tagging TV Show metadata'''
    def __init__(self, files):
        #'encodingTool': __title__, 
        self.params = {'stik': 'TV Show', 'disk': '1/1', 'comment': '', 'apID': __email__}
        self.tvdb = Tvdb(actors=True)
        self.supportedTypes = ['.mp4', '.m4v']
        self.fileCount   = len(files)
        self.fileCounter = 1
        self.buildFields(files)

    #Perform actual queries to iTunes and return results
    def doiTunesSearch(self,queries):
        parameters = {}
        search = queries['season']
        print "Searching iTunes for {}".format(search)
        #Gather Season information
        seasonResults = itunes.search_season(search)
        seasonData    = None
        try:
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
                albumArt  = seasonData.get_artwork()
                albumArt  = string.replace(albumArt['60'], "60x60-50", "600x600-75")
                parameters['artwork'] = string.replace(os.path.basename(albumArt), "\\", "").strip()
                curlCMD   = "curl -O {}".format(albumArt)
                print "Downloading Album Artwork..."
                subprocess.check_call(curlCMD, shell=True)
        except AttributeError:
            print "{} not found in iTunes".format(search)

        #Gather episode information
        search = queries['episode']
        print "Searching iTunes for {}".format(search)
        episodeResults       = itunes.search_episode(search)
        episodeData = None
        if episodeResults != []:
            episodeData = episodeResults[0]
        try:
            #Genre
            parameters['genre'] = episodeData.get_genre()
            #Genre ID
            parameters['geID']  = genreIDs[parameters['genre']]
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
        except AttributeError:
            print "{} not found in iTunes. Checking TVDB for data...".format(query)
        return parameters

    #Perform actual queries to TVDB and return results
    def doTVDBSearch(self,queries):
        pass

    def buildFields(self, files):
        if( len(files) == 0 ):
            print "No files give to tag\n"
            os._exit(os.EX_OK)
        i = 1
        for vid in files:
            extension = os.path.splitext(vid)[-1].lower()
            if extension not in self.supportedTypes:
                print "{} is not a supported file type".format(extension)
            else:
                #filename (Episode # Episode Name)
                basename = string.replace(os.path.basename(vid), "\\", "").strip()
                print "Tagging {}".format(basename)
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
                #if 'ii' in queryTitle:
                    #queryTitle = string.replace(queryTitle, "ii", "2")
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
                self.params    = dictConcat(self.params, self.doiTunesSearch(tmp))

                #TVDB query for cast, writers, director
                querySeason  = int(self.params['TVSeasonNum'])
                queryEpisode = int(self.params['TVEpisodeNum'])
                actors = []
                directors = writers = ''
                if self.params['artist'] == 'Archer':
                    self.params['artist'] = 'Archer (2009)'
                show = self.tvdb[self.params['artist']]
                for actor in show['_actors']:
                    actors.append(actor['name'])
                try:
                    episode = show[querySeason][queryEpisode]
                    try:
                        #iTunes descriptions can be terrible, use TVDB's when available
                        self.params['description'] = episode['overview'].strip()[:255]
                        #self.params['description'] = string.replace(self.params['description'], "\'", "")
                        self.params['description']   = string.replace(self.params['description'], "\"", "\\\"")
                        self.params['description']   = string.replace(self.params['description'], "\n", "")
                        #Different quote character can create AP non-zero exit status 2 problems
                        
                        #If description from TVDB is better than iTunes, use that instead
                        if len(self.params['description']) > len(self.params['longdesc']):
                            self.params['longdesc'] = self.params['description']
                        #print "episode description from TVDB: {}".format(self.params['description'])
                    except:
                        print "Unexpected error: {}, no description found".format(sys.exc_info()[0])
                    try: 
                        directors = episode['director']
                    except:
                        print "Unexpected error: {}, no directors found".format(sys.exc_info()[0])
                    #parse out director names
                    if directors != None:
                        directors = directors.split('|')
                    try:
                        writers   = episode['writer']
                    except:
                        print "Unexpected error: {}, no writers found".format(sys.exc_info()[0])
                    #parse out writer names
                    if writers != None:
                        writers   = writers.split('|')
                    #if actors != [] and directors != [] and writers != []: 
                    self.params['rDNSatom'] = createITunesXML(actors, directors, [], writers)
                    try:
                        newReleaseDate = episode['firstaired']
                        if newReleaseDate != "":
                            self.params['year'] = newReleaseDate + "T00:00:00Z"
                    except:
                        print "Unexpected error: {}, no firstaired date found on TVDB".format(sys.exc_info()[0])
                except:
                    print "Unexpected error: {}, episode not found".format(sys.exc_info()[0])
                
                if self.params['artist'] == 'Archer (2009)':
                        self.params['artist'] = 'Archer'
                #print self.params['description']
                if 'longdesc' not in self.params.keys() and 'description' in self.params.keys():
                    self.params['longdesc'] = self.params['description']
                #print self.params['longdesc']
                self.doTagging(vid, self.params)
            print "{0:.2f}% done".format(100.0*(float(self.fileCounter)/float(self.fileCount)))
            self.fileCounter += 1
            i = i + 1

class MusicTagger(Tagger):
    '''Tagger Subclass tailored to tagging Music metadata'''
    def __init__(self, files):
        self.params = {'stik': 'Music', 'disk': '1/1', 'comment': '', 'apID': __email__, 'output': 'tmp.m4a'}
        self.supportedTypes = ['.m4a']
        self.fileCount   = len(files)
        self.fileCounter = 1
        self.buildFields(files)

    def buildFields(self, files):
        if len(files) == 0:
            print "No files give to tag\n"
            os._exit(os.EX_OK)
        for song in files:
            #need to check filetype
            extension = os.path.splitext(song)[-1].lower()
            if extension not in self.supportedTypes:
                print "{} is not a supported file type".format(extension)
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
                query   = "{} {}".format(self.params['artist'], self.params['title'])
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
                    albumArt  = track.artwork
                    albumArt  = string.replace(albumArt['60'], "60x60-50", "600x600-75")
                    self.params['artwork'] = string.replace(os.path.basename(albumArt), "\\", "").strip()
                    curlCMD   = "curl -O {}".format(albumArt)
                    #print curlCMD
                    print "Downloading Album Artwork..."
                    subprocess.check_call(curlCMD, shell=True)
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
                    print "Tagging {}".format(basename)
                    self.doTagging(song, self.params)
                else:
                    print "{} not found in iTunes".format(query)

class MovieTagger(Tagger):
    '''Tagger Subclass tailored to tagging Movie metadata'''
    def __init__(self, files):
        self.params = {'stik': 'Movie', 'disk': '1/1', 'comment': '', 'apID': __email__, 'output': 'tmp.m4v'}
        self.tvdb = Tvdb(actors=True)
        self.supportedTypes = ['.mp4', '.m4v']
        self.buildFields(files)

    def buildFields(self, files):
        if( len(files) == 0 ):
            print "No files give to tag\n"
            os._exit(os.EX_OK)
        for vid in files:
            #need to check filetype
            extension = os.path.splitext(vid)[-1].lower()
            if extension not in self.supportedTypes:
                print "{} is not a supported file type".format(extension)
            else:
                #title
                self.params['title'] = string.replace(os.path.basename(vid), "\\", "").strip()[:-4]
                movieResults = itunes.search_movie(self.params['title'])
                for result in movieResults:
                    if self.params['title'].lower() in result.get_name().lower().translate(string.maketrans("",""), string.punctuation):
                        movieData = result
                        break
                if movieData:
                    #Artwork
                    artwork = movieData.get_artwork()
                    artwork = string.replace(artwork['60'], "60x60-50", "600x600-75")
                    self.params['artwork'] = string.replace(os.path.basename(artwork), "\\", "").strip()
                    curlCMD   = "curl -O {}".format(artwork)
                    subprocess.check_call(curlCMD, shell=True)
                    #Content Rating
                    self.params['contentRating'] = movieData.json['contentAdvisoryRating']
                    #Genre
                    self.params['genre'] = movieData.get_genre()
                    #Catalog ID
                    self.params['cnID']  = movieData.get_id()
                else:
                    print "{} could not be found in the iTunes Store".format(vid[:-4])
                #Insert TMDB API key here
                api_key = ''
                tmdb.configure(api_key)
                results = tmdb.Movies(self.params['title'])
                movie   = None
                for result in results.iter_results():
                    if string.replace(result['title'].lower(),":", "") == self.params['title'].lower():
                        movie = tmdb.Movie(result['id'])
                        break
                if movie != None:
                    #Release Date
                    self.params['year']        = movie.get_release_date()
                    #Short Description
                    self.params['description'] = movie.get_overview()
                    #Long Description
                    self.params['longdesc']    = movie.get_overview()
                    #If iTunes data was not found, fill in the fields from the iTunes search
                    if 'genre' not in self.params.keys():
                        self.params['genre'] = movie.get_genres()[0]['name']
                    if 'artwork' not in self.params.keys():
                        artwork = movie.get_poster()
                        self.params['artwork'] = string.replace(os.path.basename(artwork), "\\", "").strip()
                        curlCMD   = "curl -O {}".format(artwork)
                        subprocess.check_call(curlCMD, shell=True)
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
                    self.params['rDNSatom'] = createITunesXML(actors, directors, producers, writers)
                    self.doTagging(vid, self.params)

sys.exit(main())