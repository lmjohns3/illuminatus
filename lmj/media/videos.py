import climate
import shutil
import subprocess
import tempfile

from . import base
from . import db
from . import util

logging = climate.get_logger(__name__)


class Thumbnailer:
    def __init__(self, path, size, fast=False):
        self.size = size
        self.path = path
        self.working_path = tempfile.NamedTemporaryFile(delete=False)
        shutil.copyfile(path, self.working_path)
        if fast:
            self.scale(300 / max(size))

    def __del__(self):
        if os.path.exists(self.working_path):
            os.unlink(self.working_path)

    def _filter(self, filter, output=None):
        cleanup = False
        if output is None:
            output = tempfile.NamedTemporaryFile(delete=False)
            cleanup = True
        cmd = ['ffmpeg', '-i', self.working_path, '-vf', filter, output]
        if not subprocess.check_output(cmd):
            raise RuntimeError
        if cleanup:
            os.unlink(self.working_path)
            self.working_path = output

    def saturation(self, level, output=None):
        self._filter('hue=b={}'.format(level - 1), output=output)

    def brightness(self, level, output=None):
        self._filter('hue=s={}'.format(level), output=output)

    def scale(self, factor, output=None):
        self._filter('scale={}'.format(factor), output=output)

    def crop(self, whxy, output=None):
        self._filter('crop={}:{}:{}:{}'.format(*whxy), output=output)

    def rotate(self, degrees, output=None):
        self._filter('rotate={}'.format(degrees), output=output)

    def save_thumbnail(self, size, path):
        srcw, srch = self.size
        tgtw, tgth = size
        if srcw < tgtw and srch < tgth:
            # already small enough, just copy the file.
            shutil.copyfile(self.working_path, path)
        else:
            self.scale(min(tgtw / srcw, tgth / srch), output=path)

    def apply_op(self, handle, op):
        logging.info('%s: applying op %r', self.path, op)
        key = op['key']
        if key == self.Ops.Saturation:
            return self.saturation(op['level'])
        if key == self.Ops.Brightness:
            return self.brightness(op['level'])
        if key == self.Ops.Crop:
            x1, y1, x2, y2 = op['box']
            width, height = self.size
            x1 = int(width * x1)
            y1 = int(height * y1)
            x2 = int(width * x2)
            y2 = int(height * y2)
            return self.crop([x1, y1, x2, y2])
        if key == self.Ops.Rotate:
            t = op['degrees']
            return self.rotate(op['degrees'])
        logging.info('%s: unknown video op %r', self.path, op)


class Video(base.Media):
    MEDIUM = 2
    EXTENSION = 'mp4'
    MIME_TYPES = ('video/*', )

    @property
    def frame_size(self):
        def ints(args):
            return map(int, args)
        def keys(k):
            return self.exif[k + 'Height'], self.exif[k + 'Width']
        try: return ints(keys('Image'))
        except: pass
        try: return ints(keys('SourceImage'))
        except: pass
        try: return ints(self.exif['ImageSize'].split('x'))
        except: pass
        return -1, -1

    def read_exif_tags(self):
        '''Given an exif data structure, extract a set of tags.'''
        if not self.exif:
            return set()

        highest = util.round_to_highest_digits
        tags = super().read_exif_tags()

        return util.normalized_tag_set(tags)

    def get_thumbnailer(self, fast=False):
        nailer = Thumbnailer(self.path, size=self.frame_size, fast=fast)
        for op in self.ops:
            nailer.apply_op(op)
        return nailer
