import climate
import subprocess

from . import db
from . import util

logging = climate.get_logger(__name__)


class Video(object):
    MEDIUM = 2
    MIME_TYPES = ('video/*', )

    @property
    def stamp(self):
        stamp = self.meta.get('stamp')
        if not stamp:
            return None
        if isinstance(stamp, datetime.datetime):
            return stamp
        return datetime.datetime.strptime(stamp[:19], '%Y-%m-%dT%H:%M:%S')

    @property
    def thumb_path(self):
        id = '%08x' % self.id
        return os.path.join(id[:-3], '%s.mpeg' % id)

    def to_dict(self):
        return dict(id=self.id,
                    path=self.path,
                    stamp=self.stamp,
                    meta=self.meta,
                    thumb=self.thumb_path,
                    tags=list(self.tag_set))

'''
['ffmpeg', '-i', path, '-acodec', 'copy', '-vf', 'scale={0}*iw:{0}*ow', thumb]
['ffmpeg', '-i', path, '-acodec', 'copy', '-vf', 'crop=w:h:x:y', thumb]
'''
