import climate

from . import base

logging = climate.get_logger(__name__)


class Audio(base.Media):
    EXTENSION = 'mp3'
    MIME_TYPES = ('audio/*', )
