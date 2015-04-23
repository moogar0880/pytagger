# -*- coding: utf-8 -*-
import os
import re
import logging
import itunes
from trakt.tv import TVShow, TVEpisode

__author__ = 'Jon Nappi'
__all__ = ['TraktTVSearcher', 'ITunesSeasonSearcher', 'ITunesEpisodeSearcher']

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


class Callback(object):
    """A class used to encapsulate a set of keys and a callable. The process
    method will be used to extract keys from the provided instance and pass
    them into the callable
    """

    def __init__(self, keys, callback):
        self.keys, self.callback = keys, callback

    def process(self, instance):
        args = [getattr(instance, k, None) for k in self.keys]
        return self.callback(*args)


class Searcher(object):
    """Base type to define the searcher interface"""
    filter_key = ''
    key_map = {}

    def __init__(self, context):
        self.context = context
        self.logger = logging.getLogger(self.__class__.__name__)

    def _search(self, query):
        raise NotImplementedError

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

    def search(self, query, context=None):
        """Search using the provided query, and updating our instance's context
        with any additional data passed in through context
        """
        if context is None:
            context = {}
        self.context.update(context)
        return self._search(query)

    def filter_results(self, query, results):
        """Filter the results based on our filter_key"""
        for result in results:
            key = str(getattr(result, self.filter_key, None)).lower()
            if key == query.lower():
                return result
        return results[0]


class TraktTVSearcher(Searcher):
    key_map = {
        'Rating': 'certification',
        'TV Network': 'network',
        'Cast': Callback(['people'],
                         lambda people: ', '.join([person.name
                                                   for person in people
                                                   if person is not None and
                                                   person.name is not None])),
        'Genre': Callback(['genres'], lambda genres: genres[0]),
        'genreID': Callback(['genres'],
                            lambda genres: TV_GENREIDS.get(genres[0], None))
    }

    def _get_episode(self, episode):
        """Extract data from a specific episode"""
        mapping = {
            'Release Date': 'first_aired_iso',
            'Long Description': 'overview',
            'TV Show': 'show',
            'Artist': 'show',
            'Name': 'title',
            'Album Artist': 'show',
            'Album': Callback(['show', 'season'],
                              lambda show, season: '{}, Season {}'.format(
                                  show, season)
                              ),
            'Description': Callback(['overview'],
                                    lambda overview: overview[:250]),
        }
        return self._apply_mapping(episode, mapping=mapping)

    def _search(self, query):
        results = TVShow.search(query)
        slug = self.filter_results(query, results).slug
        show = TVShow(slug)
        self._apply_mapping(show)  # Get general information about the show

        # Get episode specific data
        season_num = self.context.get('TV Season', None)
        if season_num is None:
            return self.context
        episode_num = self.context.get('TV Episode #')
        episode = TVEpisode(slug, season_num, episode_num)
        return self._get_episode(episode)


class TraktMovieSearcher(Searcher):
    def _search(self, query, context=None):
        if context is not None:
            self.context.update(context)


class ITunesSeasonSearcher(Searcher):
    key_map = {
        'Artwork_URL': Callback(['get_artwork'],
                                lambda ga: ga()['60'].replace(
                                    '60x60-50', '600x600-75')
                                ),
        'Copyright': Callback(['get_copyright'], lambda cp: cp())
    }

    def filter_results(self, query, results):
        title_comparator = re.sub(r'\W+', ' ', query[:-2])
        for res in results:
            comparative_title = re.sub(r'\W+', ' ', res.artist.name)
            if title_comparator.lower() == comparative_title.lower():
                return res

    def _search(self, query):
        results = itunes.search_season(query)
        season = self.filter_results(query, results)
        return self._apply_mapping(season)


class ITunesEpisodeSearcher(Searcher):
    key_map = {
        'Genre': Callback(['get_genre'], lambda f: f()),
        'contentID': Callback(['get_episodeID'], lambda f: f()),
        'Release Date': Callback(['get_release_date'], lambda f: f()),
        'Content Rating': Callback(['get_content_rating'], lambda f: f()),
        'Long Description': Callback(['get_long_description'],
                                     lambda f: f().strip()),
        'Description': Callback(['get_short_description'],
                                lambda f: f().strip()[:255].replace('\n', '')),
    }

    def filter_results(self, query, results):
        if results:
            return results[0]
        return None

    def _search(self, query):
        results = itunes.search_episode(query)
        episode = self.filter_results(query, results)
        if episode is not None:
            return self._apply_mapping(episode)
        return self.context


class ITunesMovieSearcher(Searcher):
    def _search(self, query, context=None):
        if context is not None:
            self.context.update(context)


class ITunesMusicSearch(Searcher):
    def _filter_results(self, results):
        track = None
        for result in results:
            right_name = self.context['Name'] in result.get_name()
            right_artist = self.context['Artist'] == result.get_artist().name
            if right_name and right_artist:
                track = result
                break
        return track

    def _search(self, query, context=None):
        if context is not None:
            self.context.update(context)
        results = itunes.search_track(query)
        track = self._filter_results(results)
        if track is None:
            self.logger.error(u'{} not found in iTunes'.format(query))
            return
        self.context['Album'] = track.get_album()
        # Albumart
        url = track.get_artwork()
        url = string.replace(url['60'], '60x60-50', '600x600-75')
        if self.has_artwork(url):
            pid = str(os.getpid())
            art = os.path.abspath('.albumart{}.jpg'.format(pid))
            self.context['Artwork'] = art.replace(' ', '\\ ')
        # Genre
        self.context['Genre'] = track.get_genre()
        album = track.get_album()
        self.context['Copyright'] = album.copyright
        self.context['Track #'] = '{}/{}'.format(self.context['Track #'],
                                                 album.get_track_count())
        self.context['Release Date'] = album.get_release_date_raw()
        self.context['Album Artist'] = self.context['Artist']
        self.context['contentID'] = track.get_id()
        if track.json['trackExplicitness'].lower() == 'explicit':
            self.subler.explicitness = 'Explicit'