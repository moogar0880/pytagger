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
    #tagger = Tagger(argv)

def parseOptions():
    usage = "usage: tagger.py [options] [filenames]"
    parser = OptionParser(usage)
    parser.add_option("-t", "--TV",
                  action="store_true", dest="show",
                  help="declare media type as TV")
    parser.add_option("-m", "--Movie",
                  action="store_true", dest="movie",
                  help="declare media type as Movie")
    (options, args) = parser.parse_args()
    return options
    if options.show:
        tagger = TVTagger(argv)
    else:
        tagger = MovieTagger(argv)

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
    #def __init__(self, files, media):
    def __init__(self):
        self.supportedTypes = ['.mp4', '.m4v']

    #Build Atomic Parsley Call
    def doTagging(self, filename, params):
        command = "AtomicParsley \"{}\" --artwork REMOVE_ALL --output \"tmp.m4v\"".format(filename)
        keys = params.keys()
        for key in keys:
            #print key
            if key == 'rDNSatom':
                command += " --" + key + " \"" + str(params[key]) + "\" name=iTunMOVI domain=com.apple.iTunes"
            else:
                command += " --" + key + " \"" + str(params[key]) + "\""
        #print params['description']
        #print params['longdesc']
        #print command
        #Try to prevent those random Non-zero exit status 2 AP erorrs from halting the entire program
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
            #print command
            subprocess.check_call(command, shell=True)
            command = "mv tmp.m4v \"{}\"".format(filename)
            #print command
            subprocess.check_call(command, shell=True)
        except subprocess.CalledProcessError as e:
            print "An error occured while tagging {}. AtomicParsley Error-Code: {}".format(filename, e.returncode)

class TVTagger(Tagger):
    def __init__(self, files):
        #'encodingTool': __title__, 
        self.params = {'stik': 'TV Show', 'disk': '1/1', 'comment': '', 'apID': __email__}
        self.tvdb = Tvdb(actors=True)
        self.supportedTypes = ['.mp4', '.m4v']
        self.fileCount   = len(files)
        self.fileCounter = 1
        self.buildFields(files)

    def buildFields(self, files):
        if( len(files) == 0 ):
            print "No files give to tag\n"
            os._exit(os.EX_OK)
        for vid in files:
            #need to check filetype
            print "{0:.2f}% done".format(100.0*(float(self.fileCounter)/float(self.fileCount)))
            self.fileCounter += 1
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
                episode  = basename[:3].strip()
                #name of episode
                self.params['title'] = basename[3:-4].strip()
                #season number
                self.params['TVSeasonNum'] = seaName[-2:].strip()
                #name of show
                self.params['artist']      = os.path.basename(shoName)
                self.params['albumArtist'] = os.path.basename(shoName)
                self.params['TVShowName']  = os.path.basename(shoName)
                #format episode number
                if int(episode) < 10:
                    episode = episode[1:].encode('utf-8').strip()
                    self.params['TVEpisodeNum'] = self.params['tracknum'] = episode
                else:
                    self.params['TVEpisodeNum'] = self.params['tracknum'] = episode.encode('utf-8').strip()
                #format episode ID
                self.params['TVEpisode'] = "S{}E{}".format(self.params['TVSeasonNum'], self.params['TVEpisodeNum'])
                #format album name
                self.params['album'] = "{}, Season {}".format(self.params['artist'], self.params['TVSeasonNum'])
                #setup and perform iTunes query
                iTunesQuery          = "{} {}".format(self.params['artist'], self.params['TVSeasonNum'])
                print "Searching iTunes for {}".format(iTunesQuery)
                seasonResults        = itunes.search_season(iTunesQuery)
                queryTitle = self.params['title'].lower() 
                #queryTitle = (string.replace(title.lower(), "the ", "")).strip()
                queryTitle = (string.replace(queryTitle, "-", " ")).strip()
                if 'ii' in queryTitle:
                    queryTitle = string.replace(queryTitle, "ii", "2")
                if 'part ' in queryTitle:
                    queryTitle = string.replace(queryTitle, "part ", "pt ")
                if 'fuckers' in queryTitle:
                    queryTitle = string.replace(queryTitle, "fuckers", "fu*kers")
                if 'fucker' in queryTitle:
                    queryTitle = string.replace(queryTitle, "fucker", "f*****")
                if 'fuck' in queryTitle:
                    queryTitle = string.replace(queryTitle, "fuck", "f***")

                #... -> ,
                #II -> 2
                #1/2 or and a half -> 

                query    = "{} {}".format(self.params['TVShowName'], queryTitle)
                print "Searching iTunes for {}".format(query)
                #iTunesQuery          = "{} {}".format(self.params['artist'], self.params['title'].lower())
                episodeResults       = itunes.search_episode(query)
                episodeData = seasonData = None
                '''if seasonResults != {}:
                    titleLength = self.params['artist'].__len__()
                    for result in seasonResults:
                        if result.get_name()[:titleLength].strip() == self.params['artist'] and result.get_name()[-1:] == self.params['TVSeasonNum']:
                            seasonData = result'''
                seasonData = seasonResults[0]
                episodeResults = sorted(episodeResults, key=lambda episode: episode.episode_number)
                #for result in episodeResults:
                    #if result.get_season() == self.params['TVSeasonNum'] and result.get_episode_num() == int(episode):
                        #episodeData = result
                if episodeResults != []:
                    episodeData = episodeResults[0]
                #if seasonData:
                #    print seasonData
                #else:
                #    print "{} could not be found on iTunes checking TVDB...".format(query)
                #Copyright info
                self.params['copyright'] = seasonData.get_copyright()
                albumArt  = seasonData.get_artwork()
                albumArt  = string.replace(albumArt['60'], "60x60-50", "600x600-75")
                #print albumArt
                self.params['artwork'] = string.replace(os.path.basename(albumArt), "\\", "").strip()
                #print self.params['artwork']
                curlCMD   = "curl -O {}".format(albumArt)#curl -O albumArt #will download image, filename will be the filename from url (ie everything after the last /)
                #print curlCMD
                print "Downloading Album Artwork..."
                subprocess.check_call(curlCMD, shell=True)
                querySeason  = int(self.params['TVSeasonNum'])
                queryEpisode = int(self.params['TVEpisodeNum'])
                #Genre
                try:
                    self.params['genre'] = episodeData.get_genre()
                    #Genre ID
                    self.params['geID']  = genreIDs[self.params['genre']]
                    #Release Date
                    self.params['year']  = episodeData.get_release_date()
                    #short description, max length 255 characters
                    self.params['description']   = episodeData.get_short_description().strip()[:255]
                    #self.params['description']   = string.replace(self.params['description'], "\'", "")
                    self.params['description']   = string.replace(self.params['description'], "\"", "\\\"")
                    #long description
                    self.params['longdesc']      = episodeData.get_long_description().strip()
                    #self.params['longdesc']      = string.replace(self.params['longdesc'], "\'", "")
                    #catalog ID
                    self.params['cnID']          = episodeData.get_episodeID()
                    #content rating
                    self.params['contentRating'] = episodeData.get_content_rating()
                except AttributeError:
                    print "{} not found in iTunes. Checking TVDB for data...".format(query)

                #TVDB query for cast, writers, director
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
                
            #else: #if not found on iTunes check TVDB
                #print "{} could not be found on iTunes".format(query)
                if self.params['artist'] == 'Archer (2009)':
                        self.params['artist'] = 'Archer'
                print self.params['description']
                print self.params['longdesc']
                Tagger.doTagging(self, vid, self.params)

class MovieTagger(Tagger):
    def __init__(self, files):
        self.params = {'stik': 'Movie', 'disk': '1/1', 'comment': '', 'encodingTool': __title__, 'apID': __email__, 'output': 'tmp.m4v'}
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
                self.params['title'] = vid[:-4]
                movieResults = itunes.search_movie(self.params['title'])
                movieData = None
                for result in movieResults:
                    if result == self.params['title']:
                        movieData = result
                        break
                if movieData != None:
                    #Release Date
                    self.params['year'] = movieData.get_release_date_raw()
                    #Artwork
                    artwork = movieData.get_artwork()
                    artwork = string.replace(artwork['60'], "60x60-50", "600x600-75")
                    self.params['artwork'] = string.replace(os.path.basename(albumArt), "\\", "").strip()
                    curlCMD   = "curl -O {}".format(albumArt)#curl -O albumArt #will download image, filename will be the filename from url (ie everything after the last /)
                    subprocess.check_call(curlCMD, shell=True)
                    #Content Rating
                    self.params['contentRating'] = movieData.json['contentAdvisoryRating']
                    #Genre
                    self.params['genre'] = movieData.get_genre()
                    #Catalog ID
                    self.params['cnID'] = movieData.get_id()
                    #Short Description
                    #Long Description
                    #Actors
                    #Directors
                    #Writers
                    #Producers
                    Tagger.doTagging(self, vid, self.params)
                else:
                    print "{} could not be found in the iTunes Store".format(vid[:-4])

sys.exit(main())



































