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
except ImportError:
    print 'tvdb_api not installed'    

__name__       = 'pytagger'
__doc__        = 'A python backend to iTunes style metadata tagging'
__author__     = 'Jonathan Nappi'
__version__    = '0.1'
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
    tagger = Tagger(argv, mediaType)

def parseOptions():
    usage = "usage: tagger.py [options] [filenames]"
    parser = OptionParser(usage)
    parser.add_option("-t", "--TV",
                  action="store_true", dest="tvType",
                  help="declare media type as TV")
    parser.add_option("-m", "--Movie", 
                  action="store_true", dest="mvType",
                  help="declare media type as Movie")
    (options, args) = parser.parse_args()
    if options.tvType:
        return True
    else:
        return False

def createITunesXML(cast, directors, producers, writers):
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD\ PLIST\ 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
'''
    if cast != []:
        xml += "\t<key>cast</key>\n\t<array>\n"
        for name in cast:
            xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    if directors != []:
        xml += "\t<key>directors</key>\n\t<array>\n"
        for name in directors:
            xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    if producers != []:
        xml += "\t<key>producers</key>\n\t<array>\n"
        for name in producers:
            xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    if writers != []:
        xml += "\t<key>screenwriters</key>\n\t<array>\n"
        for name in writers:
            xml += "\t\t<dict>\n\t\t\t<key>name</key>\n\t\t\t<string>{}</string>\n\t\t</dict>\n".format(name)
        xml += "\t</array>\n"

    xml += "</dict>\n</plist>\n"
    return xml

class Tagger():
    def __init__(self, files, media):
        self.show = self.movie = False
        if media:
            self.show  = True
        else:
            self.movie = True
        self.supportedTypes = ['.mp4', '.m4v']
        self.tag(files)

    def tag(self, files):
        if( len(files) == 0 ):
            print "No files give to tag\n"
            os._exit(os.EX_OK)
        for vid in files:
            #need to check filetype
            extension = os.path.splitext(vid)[-1].lower()
            if extension not in self.supportedTypes:
                print "{} is not a supported file type".format(extension)
                sys.exit(EX_DATAERR)
            basename = string.replace(os.path.basename(vid), "\\", "").strip() #filename
            seaName  = string.replace(os.path.dirname(vid), "\\", "")          #folder containing file
            shoName  = string.replace(os.path.dirname(seaName), "\\", "")      #folder containing folder
            title    = basename[3:-4].strip()   #name of episode
            episode  = basename[:3].strip()     #episode number
            season   = seaName[-2:].strip()     #season number
            show     = os.path.basename(shoName)#name of show
            epID     = "S{}E{}".format(season, episode)     #format episode ID
            if int(episode) < 10:
                episode = episode[1:].encode('utf-8').strip()
            else:
                episode.encode('utf-8').strip()
            album    = "{}, Season {}".format(show, season) #format album name
            tmpFile  = "tmp.m4v" #specify the filename of tempfile (voids overWrite)
            query    = "{} season {}".format(show, season)
            seasonResults  = itunes.search_season(query)
            episodeResults = itunes.search_episode(query)
            episodeData = seasonData = None
            if seasonResults == {}: #check TVDB
                print "{} could not be found on iTunes".format(query)

            titleLength = show.__len__()
            for result in seasonResults:
                if result.get_name()[:titleLength].strip() == show and result.get_name()[-1:] == season:
                    seasonData = result
            episodeResults = sorted(episodeResults, key=lambda episode: episode.episode_number)
            for result in episodeResults:
                if result.get_season() == season and result.get_episode_num() == int(episode):
                    episodeData = result

            #if seasonData:
            #    print seasonData
            #else:
            #    print "{} could not be found on iTunes checking TVDB...".format(query)
            copyright = seasonData.get_copyright()
            albumArt  = seasonData.get_artwork()
            albumArt  = string.replace(albumArt['60'], "60x60-50", "600x600-75")
            artFileName = string.replace(os.path.basename(albumArt), "\\", "").strip()
            curlCMD = "curl -O {}".format(albumArt)#curl -O albumArt #will download image, filename will be the filename from url (ie everything after the last /)
            subprocess.check_call(curlCMD, shell=True)
            genre     = episodeData.get_genre()
            genreID   = genreIDs[genre]
            date      = episodeData.get_release_date()
            shortDescription = episodeData.get_short_description().strip()
            longDescription  = episodeData.get_long_description().strip()
            catalogID        = episodeData.get_episodeID()
            contentRating    = episodeData.get_content_rating()
            #TVDB query for cast, writers, director
            tvdb = Tvdb(actors=True)
            actors = []
            for actor in tvdb[show]['_actors']:
                actors.append(actor['name'])
            #CAN be multiple directors
            directors = tvdb[show][int(season)][int(episode)]['director'] #need to parse out name(s)
            directors = directors.split('|')
            #print directors
            #multiple writers
            writers   = tvdb[show][int(season)][int(episode)]['writer'] #need to parse out name(s)
            writers   = writers.split('|')
            
            xml = createITunesXML(actors, directors, [], writers)

            #build AtomicParsley call
            command  = ("AtomicParsley \"{}\" --stik \"{}\" --artist \"{}\" --album" + 
                        " \"{}\" --tracknum {}/ --disk 1/1 --albumArtist" + 
                        " \"{}\" --TVEpisode {} --comment \"\" --year \"{}\"" + 
                        " --description \"{}\" --longdesc \"{}\" --TVShowName \"{}\"" + 
                        " --TVSeasonNum \"{}\" --TVEpisodeNum \"{}\" " +
                        " --title \"{}\" --cnID {} --geID {} --apID \"{}\" --encodingTool \"{}\"" +
                        " --genre \"{}\" --copyright \"{}\" --output \"{}\" --contentRating \"{}\"" + 
                        " --artwork REMOVE_ALL --artwork \"{}\" --rDNSatom \"{}\" name=iTunMOVI domain=com.apple.iTunes"
                        "").format(vid, "TV Show", show, album, episode, show, epID, date, 
                                   shortDescription, longDescription, show, season, episode, 
                                   title, catalogID, genreID, __email__, __title__, genre,
                                   copyright, tmpFile, contentRating, artFileName, xml)
            #print command
            subprocess.check_call(command, shell=True)
            subprocess.check_call("rm {}".format(artFileName), shell=True)#delete artfile
            command = "mv \"{}\" \"{}\"-old".format(vid, vid)
            #print command
            subprocess.check_call(command, shell=True)
            command = "mv tmp.m4v \"{}\"".format(vid)
            #print command
            subprocess.check_call(command, shell=True)

sys.exit(main())