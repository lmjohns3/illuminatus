import climate
import os

from . import base
from . import db
from . import util

logging = climate.get_logger(__name__)


class Video(base.Media):
    EXTENSION = 'mp4'
    MIME_TYPES = ('video/*', )

    @property
    def frame_size(self):
        def ints(args):
            return int(args[0]), int(args[1])

        def keys(k):
            return self.meta[k + 'Width'], self.meta[k + 'Height']

        try:
            return ints(keys('Image'))
        except:
            pass
        try:
            return ints(keys('SourceImage'))
        except:
            pass
        try:
            return ints(self.meta['ImageSize'].split('x'))
        except:
            pass

        return -1, -1

    def _refresh_thumbnails(self):
        output = util.ensure_path(self.db.root, self.thumb)
        tools.Ffmpeg(self.path).thumbnail(shape, output)
