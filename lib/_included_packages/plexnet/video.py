import plexobjects
import media
import plexmedia
import plexstream
import exceptions
import compat


class Video(media.MediaItem):
    TYPE = None

    def __init__(self, *args, **kwargs):
        self._settings = None
        media.MediaItem.__init__(self, *args, **kwargs)

    @property
    def settings(self):
        if not self._settings:
            import plexapp
            self._settings = plexapp.PlayerSettingsInterface()

        return self._settings

    def selectedAudioStream(self):
        if self.audioStreams:
            for stream in self.audioStreams:
                if stream.isSelected():
                    return stream
        return None

    def selectedSubtitleStream(self):
        if self.subtitleStreams:
            for stream in self.subtitleStreams:
                if stream.isSelected():
                    return stream
        return None

    def selectStream(self, stream, async=True):
        self.mediaChoice.part.setSelectedStream(stream.streamType.asInt(), stream.id, async)

    def isVideoItem(self):
        return True

    def _findStreams(self, streamtype):
        streams = []
        for media_ in self.media():
            for part in media_.parts:
                for stream in part.streams:
                    if stream.streamType.asInt() == streamtype:
                        streams.append(stream)
        return streams

    def analyze(self):
        """ The primary purpose of media analysis is to gather information about that media
            item. All of the media you add to a Library has properties that are useful to
            know - whether it's a video file, a music track, or one of your photos.
        """
        self.server.query('/%s/analyze' % self.key)

    def markWatched(self):
        path = '/:/scrobble?key=%s&identifier=com.plexapp.plugins.library' % self.ratingKey
        self.server.query(path)
        self.reload()

    def markUnwatched(self):
        path = '/:/unscrobble?key=%s&identifier=com.plexapp.plugins.library' % self.ratingKey
        self.server.query(path)
        self.reload()

    # def play(self, client):
    #     client.playMedia(self)

    def refresh(self):
        self.server.query('%s/refresh' % self.key, method=self.server.session.put)

    def _getStreamURL(self, **params):
        if self.TYPE not in ('movie', 'episode', 'track'):
            raise exceptions.Unsupported('Fetching stream URL for %s is unsupported.' % self.TYPE)
        mvb = params.get('maxVideoBitrate')
        vr = params.get('videoResolution')

        # import plexapp

        params = {
            'path': self.key,
            'offset': params.get('offset', 0),
            'copyts': params.get('copyts', 1),
            'protocol': params.get('protocol', 'hls'),
            'mediaIndex': params.get('mediaIndex', 0),
            'directStream': '1',
            'directPlay': '0',
            'X-Plex-Platform': params.get('platform', 'Chrome'),
            # 'X-Plex-Platform': params.get('platform', plexapp.INTERFACE.getGlobal('platform')),
            'maxVideoBitrate': max(mvb, 64) if mvb else None,
            'videoResolution': '{0}x{1}'.format(*vr) if vr else None
        }

        final = {}

        for k, v in params.items():
            if v is not None:  # remove None values
                final[k] = v

        streamtype = 'audio' if self.TYPE in ('track', 'album') else 'video'
        server = self.getTranscodeServer(True, self.TYPE)

        return server.buildUrl('/{0}/:/transcode/universal/start.m3u8?{1}'.format(streamtype, compat.urlencode(final)), includeToken=True)
        # path = "/video/:/transcode/universal/" + command + "?session=" + AppSettings().GetGlobal("clientIdentifier")


@plexobjects.registerLibType
class Movie(Video):
    TYPE = 'movie'

    def _setData(self, data):
        Video._setData(self, data)
        if self.isFullObject():
            self.collections = plexobjects.PlexItemList(data, media.Collection, media.Collection.TYPE, server=self.server)
            self.countries = plexobjects.PlexItemList(data, media.Country, media.Country.TYPE, server=self.server)
            self.directors = plexobjects.PlexItemList(data, media.Director, media.Director.TYPE, server=self.server)
            self.genres = plexobjects.PlexItemList(data, media.Genre, media.Genre.TYPE, server=self.server)
            self.media = plexobjects.PlexMediaItemList(data, plexmedia.PlexMedia, media.Media.TYPE, initpath=self.initpath, server=self.server, media=self)
            self.producers = plexobjects.PlexItemList(data, media.Producer, media.Producer.TYPE, server=self.server)
            self.roles = plexobjects.PlexItemList(data, media.Role, media.Role.TYPE, server=self.server)
            self.writers = plexobjects.PlexItemList(data, media.Writer, media.Writer.TYPE, server=self.server)

        self._videoStreams = None
        self._audioStreams = None
        self._subtitleStreams = None

        # data for active sessions
        self.sessionKey = plexobjects.PlexValue(data.attrib.get('sessionKey', ''), self)
        self.user = self._findUser(data)
        self.player = self._findPlayer(data)
        self.transcodeSession = self._findTranscodeSession(data)

    @property
    def videoStreams(self):
        if self._videoStreams is None:
            self._videoStreams = self._findStreams('videostream')
        return self._videoStreams

    @property
    def audioStreams(self):
        if self._audioStreams is None:
            self._audioStreams = self._findStreams('audiostream')
        return self._audioStreams

    @property
    def subtitleStreams(self):
        if self._subtitleStreams is None:
            self._subtitleStreams = self._findStreams('subtitlestream')
        return self._subtitleStreams

    @property
    def actors(self):
        return self.roles

    @property
    def isWatched(self):
        return self.viewCount > 0

    def getStreamURL(self, **params):
        return self._getStreamURL(**params)


@plexobjects.registerLibType
class Show(Video):
    TYPE = 'show'

    def _setData(self, data):
        Video._setData(self, data)
        if self.isFullObject():
            self.genres = plexobjects.PlexItemList(data, media.Genre, media.Genre.TYPE, server=self.server)
            self.roles = plexobjects.PlexItemList(data, media.Role, media.Role.TYPE, server=self.server)

    @property
    def isWatched(self):
        return self.viewedLeafCount == self.leafCount

    def seasons(self):
        path = '/library/metadata/%s/children' % self.ratingKey
        return plexobjects.listItems(self.server, path, Season.TYPE)

    def season(self, title):
        path = '/library/metadata/%s/children' % self.ratingKey
        return plexobjects.findItem(self.server, path, title)

    def episodes(self, watched=None):
        leavesKey = '/library/metadata/%s/allLeaves' % self.ratingKey
        return plexobjects.listItems(self.server, leavesKey, watched=watched)

    def episode(self, title):
        path = '/library/metadata/%s/allLeaves' % self.ratingKey
        return plexobjects.findItem(self.server, path, title)

    def watched(self):
        return self.episodes(watched=True)

    def unwatched(self):
        return self.episodes(watched=False)

    def get(self, title):
        return self.episode(title)

    def refresh(self):
        self.server.query('/library/metadata/%s/refresh' % self.ratingKey)


@plexobjects.registerLibType
class Season(Video):
    TYPE = 'season'

    @property
    def isWatched(self):
        return self.viewedLeafCount == self.leafCount

    def episodes(self, watched=None):
        childrenKey = '/library/metadata/%s/children' % self.ratingKey
        return plexobjects.listItems(self.server, childrenKey, watched=watched)

    def episode(self, title):
        path = '/library/metadata/%s/children' % self.ratingKey
        return plexobjects.findItem(self.server, path, title)

    def get(self, title):
        return self.episode(title)

    def show(self):
        return plexobjects.listItems(self.server, self.parentKey)[0]

    def watched(self):
        return self.episodes(watched=True)

    def unwatched(self):
        return self.episodes(watched=False)


@plexobjects.registerLibType
class Episode(Video):
    TYPE = 'episode'

    def _setData(self, data):
        Video._setData(self, data)
        if self.isFullObject():
            self.directors = plexobjects.PlexItemList(data, media.Director, media.Director.TYPE, server=self.server)
            self.media = plexobjects.PlexMediaItemList(data, plexmedia.PlexMedia, media.Media.TYPE, initpath=self.initpath, server=self.server, media=self)
            self.writers = plexobjects.PlexItemList(data, media.Writer, media.Writer.TYPE, server=self.server)

        self._videoStreams = None
        self._audioStreams = None
        self._subtitleStreams = None

        # data for active sessions
        self.sessionKey = plexobjects.PlexValue(data.attrib.get('sessionKey', ''), self)
        self.user = self._findUser(data)
        self.player = self._findPlayer(data)
        self.transcodeSession = self._findTranscodeSession(data)

    @property
    def defaultThumb(self):
        return self.grandparentThumb or self.parentThumb or self.thumb

    @property
    def videoStreams(self):
        if self._videoStreams is None:
            self._videoStreams = self._findStreams(plexstream.PlexStream.TYPE_VIDEO)
        return self._videoStreams

    @property
    def audioStreams(self):
        if self._audioStreams is None:
            self._audioStreams = self._findStreams(plexstream.PlexStream.TYPE_AUDIO)
        return self._audioStreams

    @property
    def subtitleStreams(self):
        if self._subtitleStreams is None:
            self._subtitleStreams = self._findStreams(plexstream.PlexStream.TYPE_SUBTITLE)
        return self._subtitleStreams

    @property
    def isWatched(self):
        return self.viewCount > 0

    def getStreamURL(self, **params):
        return self._getStreamURL(**params)

    def season(self):
        return plexobjects.listItems(self.server, self.parentKey)[0]

    def show(self):
        return plexobjects.listItems(self.server, self.grandparentKey)[0]


@plexobjects.registerLibType
class Clip(Video):
    TYPE = 'clip'

    @property
    def isWatched(self):
        return self.viewCount > 0

    def getStreamURL(self, **params):
        return self._getStreamURL(**params)
