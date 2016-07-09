# -*- coding: utf-8 -*-
import os
import re
import itunes
import requests

from asyncio.log import logger as LOGGER
from trakt.movies import Movie
from trakt.tv import TVShow, TVEpisode
from trakt.utils import slugify
from uuid import uuid4

__author__ = 'Jon Nappi'
__all__ = ['TraktTVSearcher', 'ITunesSeasonSearcher', 'ITunesEpisodeSearcher']

TV_GENREIDS = {'Comedy': 4000, 'Drama': 4001, 'Animation': 4002,
               'Action & Adventure': 4003, 'Classic': 4004, 'Kids': 4005,
               'Nonfiction': 4006, 'Reality TV': 4007,
               'Sci-Fi & Fantasy': 4008, 'Sports': 4009, 'Teens': 4010,
               'Latino TV': 4011}
# inject trakt genre variables into their itunes equivalents
TV_GENREIDS['Fantasy'] = 4008

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
# inject trakt genre variables into their itunes equivalents
MOVIE_GENREIDS['Fantasy'] = 4413

#: ITUNES_DATE_FMT is the format string for an iTunes timestamp
ITUNES_DATE_FMT = '%Y-%m-%dT%H:%M:%SZ'

class Callback(object):
    """A class used to encapsulate a set of keys and a callable. The process
    method will be used to extract keys from the provided instance and pass
    them into the callable
    """

    def __init__(self, keys, callback):
        self.keys, self.callback = keys, callback

    def process(self, instance):
        args = [getattr(instance, k, None) for k in self.keys]
        if any([a is None for a in args]):
            return None
        return self.callback(*args)


class Searcher(object):
    """Base type to define the searcher interface"""
    filter_key = ''
    key_map = {}

    def __init__(self, context):
        self.context = context

    def _search(self, query):
        raise NotImplementedError()

    def _apply_mapping(self, instance, mapping=None):
        """Apply the key mapping using *instance*"""
        if mapping is None:
            mapping = self.key_map

        for key, val in mapping.items():
            if isinstance(val, Callback):
                self.context[key] = val.process(instance)
            else:
                self.context[key] = getattr(instance, val, None)
        return self.context

    def parse_query(self, parser):
        raise NotImplementedError(self.__class__.__name__)

    def has_artwork(self, url):
        """Attempts to download artwork from the provided URL and write it to a
        .jpg file named '.albumart.jpg' then return True as long as a 2xx HTTP
        response is recieved. If an error should occur, nothing is downloaded
        and False is returned
        """
        if not url:
            return False
        LOGGER.info('Downloading Album Artwork...')
        LOGGER.debug('URL: %s', url)
        req = requests.get(url)
        if 200 <= req.status_code < 300:
            file_name = '.albumart{}.jpg'.format(str(uuid4()))
            LOGGER.info('Writing artwork to %s', file_name)
            with open(file_name, 'wb') as f:
                f.write(req.content)
            return file_name.replace(' ', '\\ ')
        message = 'Album Art Not Downloaded: {}'.format(req.status_code)
        LOGGER.warn(message)
        return False

    def search(self, parser, context=None):
        """Search using the provided query, and updating our instance's context
        with any additional data passed in through context
        """
        if context is None:
            context = {}
        self.context.update(context)
        query = self.parse_query(parser)
        res = self._search(query)

        # if the Artwork_URL field was set into the returned context, then
        # fetch said artwork and set the Artwork Atom to point to it
        if 'Artwork_URL' in res:
            url = res.pop('Artwork_URL')
            artwork = self.has_artwork(url.value)
            if url.value and artwork:
                res['Artwork'] = artwork
        return res

    def filter_results(self, query, results):
        """Filter the results based on our filter_key"""
        for result in results:
            key = str(getattr(result, self.filter_key, None)).lower()
            if key == query.lower():
                return result
        return results[0]


class TraktTVSearcher(Searcher):
    """Search for data on a particular tv season (and episode) in trakt"""
    key_map = {
        'Rating': 'certification',
        'TV Network': 'network',
        'Cast': Callback(['people'],
                         lambda people: ', '.join([person.name
                                                   for person in people
                                                   if person is not None and
                                                   person.name is not None])),
        'Genre': Callback(['genres'], lambda genres: genres[0].title()),
        'genreID': Callback(['genres'],
                            lambda genres: TV_GENREIDS.get(genres[0].title()))
    }

    def _get_episode(self, episode):
        """Extract data from a specific episode"""
        mapping = {
            'Long Description': 'overview',
            'Name': 'title',
            'Release Date': Callback(['first_aired_date'],
                                     lambda fa: fa.strftime(ITUNES_DATE_FMT)),
            'Description': Callback(['overview'],
                                    lambda overview: overview[:250]),
        }
        return self._apply_mapping(episode, mapping=mapping)

    def parse_query(self, parser):
        show, season, episode, title = parser.parse()
        show = os.path.basename(show)
        if show.islower():
            show = show.title()
        self.context['Name'], self.context['TV Season'] = title, season
        for tag in ['Artist', 'Album Artist', 'TV Show']:
            self.context[tag] = show
        self.context['TV Episode #'] = self.context['Track #'] = episode
        self.context['TV Episode ID'] = 'S{}E{}'.format(season, episode)
        self.context['Album'] = '{}, Season {}'.format(show, season)
        LOGGER.debug('Trakt Query: %s', show)
        return show

    def _search(self, query):
        """Search Trakt for a TV episode matching *query*"""
        results = TVShow.search(query)
        self.filter_key = slugify(query)
        slug = self.filter_results(query, results).slug
        show = TVShow(slug)
        LOGGER.info('Trakt Search Result: %s', str(show))
        self._apply_mapping(show)  # Get general information about the show

        # Get episode specific data
        season_num = self.context.get('TV Season', None)
        if season_num is None:
            return self.context
        episode_num = self.context.get('TV Episode #')
        episode = TVEpisode(slug, season_num, episode_num)
        return self._get_episode(episode)


class TraktMovieSearcher(Searcher):
    key_map = {
        'Description': 'overview',
        'Long Description': 'overview',
        'Rating': 'certification',
        'Cast': Callback(['people'],
                         lambda people: ', '.join([person.name
                                                   for person in people
                                                   if person is not None and
                                                   person.name is not None])),
        'Genre': Callback(['genres'], lambda genres: genres[0].title()),
        'genreID': Callback(['genres'],
                            lambda genres: TV_GENREIDS.get(genres[0].title()))
    }

    def parse_query(self, parser):
        title, year = parser.parse()
        if title.islower():
            title = title.title()
        self._title, self._year = title, year
        self.context['Name'] = title
        if year:
            self.context['Name'] = '{title} ({year})'.format(title=title,
                                                             year=year)
        return title

    def _filter_results(self, query, results):
        """Filter our search results to find a movie matching *query*"""
        import pdb; pdb.set_trace()
        for result in results:
            if self._title.lower() == result.title.lower():
                if self._year is not None and self._year == result.year:
                    return result
        return results[0]

    def _search(self, query, context=None):
        """Search for a movie matching *query*"""
        results = Movie.search(query)
        movie = self._filter_results(query, results)
        movie._get()  # fetch remainder of data from trakt
        if movie is not None:
            return self._apply_mapping(movie)
        return self.context


class ITunesSeasonSearcher(Searcher):
    """Search for data on a particular season in itunes"""
    key_map = {
        'Artwork_URL': Callback(['artwork'],
                                lambda artwork: artwork.get('600')),
        'Copyright': 'copyright',
    }

    def parse_query(self, parser):
        show, season, episode, title = parser.parse()
        show = os.path.basename(show)
        if show.islower():
            show = show.title()
        self.context['Name'], self.context['TV Season'] = title, season
        for tag in ['Artist', 'Album Artist', 'TV Show']:
            self.context[tag] = show
        self.context['TV Episode #'] = self.context['Track #'] = episode
        self.context['TV Episode ID'] = 'S{}E{}'.format(season, episode)
        # Format album name
        artist = self.context.get('Artist', '')
        album_title = '{}, Season {}'.format(artist, season)
        self.context['Album'] = album_title
        return '{show} {season}'.format(show=show, season=season)

    def filter_results(self, query, results):
        """Filter out results matching *query*. Replace whitespace characters
        and compare lowercase versions of the titles to determine if we found
        a match.
        """
        title_comparator = re.sub(r'\W+', ' ', query[:-2])
        for res in results:
            comparative_title = re.sub(r'\W+', ' ', res.artist.name)
            if title_comparator.lower() == comparative_title.lower():
                return res

    def _search(self, query):
        """Search itunes for a TV Season matching *query*"""
        results = itunes.search_season(query)
        season = self.filter_results(query, results)
        return self._apply_mapping(season)


class ITunesEpisodeSearcher(Searcher):
    """Search for data on a particular episode in itunes"""
    key_map = {
        'Genre': 'primary_genre_name',
        'genreID': Callback(['primary_genre_name'],
                            lambda pgn: TV_GENREIDS.get(pgn.title(), None)),
        'contentID': 'track_id',
        'Release Date': 'release_date',
        'Long Description': 'long_description',
        'Description': 'short_description',
        '_explicit': Callback(['json'],
                              lambda jsn: jsn.get('trackExplicitness'))
    }

    def parse_query(self, parser):
        show, season, episode, title = parser.parse()
        show = os.path.basename(show)
        if show.islower():
            show = show.title()
        return '{show} {title}'.format(show=show, title=title)

    def filter_results(self, query, results):
        """There are a lot of factors involved in processing episodes, for now
        just grab the first one returned and hope Apple knew what we were
        looking for.
        """
        if results:
            return results[0]
        return None

    def _search(self, query):
        """Search iTunes for a TV Episode matching *query*"""
        results = itunes.search_episode(query)
        episode = self.filter_results(query, results)
        LOGGER.info('iTunes Search Result: %s', str(episode))
        if episode is not None:
            return self._apply_mapping(episode)
        return self.context


class ITunesMovieSearcher(Searcher):
    """Search for data on a particular movie in itunes"""
    key_map = {
        'Genre': 'primary_genre_name',
        'genreID': Callback(['primary_genre_name'],
                            lambda pgn: TV_GENREIDS.get(pgn.title(), None)),
        'contentID': 'track_id',
        'Release Date': 'release_date_raw',
        'Long Description': 'long_description',
        'Description': 'short_description',
        '_explicit': Callback(['json'],
                              lambda jsn: jsn.get('trackExplicitness'))
    }

    def parse_query(self, parser):
        title, year = parser.parse()
        if title.islower():
            title = title.title()

        if year:
            self.context['Name'] = '{title} ({year})'.format(title=title,
                                                             year=year)
            return '{title} {year}'.format(title=title, year=year)
        self.context['Name'] = title
        return title

    def _filter_results(self, results):
        if results:
            return results[0]
        return None

    def _search(self, query, context=None):
        if context is not None:
            self.context.update(context)
        results = itunes.search_movie(query)
        movie = self._filter_results(results)
        LOGGER.info('iTunes Search Result: %s', str(movie))
        return self._apply_mapping(movie)


class ITunesMusicSearch(Searcher):
    """Searcher used to query the iTunes store API for an album track"""

    def _filter_results(self, results):
        """Filter the iTunes API results from a collection of api results"""
        track = None
        for result in results:
            right_name = self.context['Name'] in result.name
            right_artist = self.context['Artist'] == result.artist.name
            if right_name and right_artist:
                track = result
                break
        return track

    def _search(self, query, context=None):
        """Search the iTunes API for an album track matching the provided query
        """
        if context is not None:
            self.context.update(context)
        results = itunes.search_track(query)
        track = self._filter_results(results)
        LOGGER.info('iTunes Search Result: %s', str(track))
        if track is None:
            LOGGER.error('{} not found in iTunes'.format(query))
            return
        self.context.update(dict(Album=track.album,
                                 Genre=track.genre,
                                 contentID=track.id,
                                 Copyright=track.album.copyright))
        # Albumart
        url = track.artwork.get('600', '')
        artwork = self.has_artwork(url.value)
        if artwork:
            self.context['Artwork'] = artwork
        self.context['Track #'] = '{}/{}'.format(self.context['Track #'],
                                                 track.album.track_count)
        self.context['Release Date'] = track.album.release_date_raw
        self.context['Album Artist'] = self.context['Artist']
        if track.json['trackExplicitness'].lower() == 'explicit':
            self.context['_explicit'] = 'Explicit'
