import climate
import io
import os

from . import base
from . import util

logging = climate.get_logger(__name__)

_CAMERAS = 'canon nikon kodak digital camera super powershot'.split()


class Photo(base.Media):
    EXTENSION = 'jpg'
    MIME_TYPES = ('image/*', )

    def _refresh_thumbnail(self):
        output = util.ensure_path(self.db.root, self.thumb)
        tools.Convert(self.path).thumbnail(shape, output)
