import climate
import os
import shutil
import subprocess
import tempfile
import uuid

from . import base
from . import db
from . import util

logging = climate.get_logger(__name__)


def mktemp():
    return os.path.join(tempfile.gettempdir(), uuid.uuid4().hex + '.mp4')


class Thumbnailer:
    def __init__(self, path, size, fast=True):
        self.size = self.working_size = size
        self.path = path
        self.working_path = mktemp()
        os.symlink(path, self.working_path)
        if fast:
            audio = '-c:a libfaac -b:a 80k'
            video = '-c:v libx264 -preset veryfast -crf 28'
            self.scale(800 / size[1], audio=audio.split(), video=video.split())

    def __del__(self):
        if os.path.exists(self.working_path):
            os.unlink(self.working_path)

    def _filter(self, filter, output=None, audio=(), video=()):
        cleanup = False
        if output is None:
            output = mktemp()
            cleanup = True
        cmd = ['ffmpeg', '-i', self.working_path]
        cmd.extend(audio)
        cmd.extend(video)
        cmd.extend(['-vf', filter, output])
        logging.debug('%s: running ffmpeg\n%s', self.path, ' '.join(cmd))
        subprocess.check_output(cmd, stderr=subprocess.PIPE)
        if cleanup:
            os.unlink(self.working_path)
            self.working_path = output

    def saturation(self, level, **kwargs):
        self._filter('hue=b={}'.format(level - 1), **kwargs)

    def brightness(self, level, **kwargs):
        self._filter('hue=s={}'.format(level), **kwargs)

    def scale(self, factor, **kwargs):
        w, h = self.working_size
        w = int(factor * w)
        w -= w % 2
        h = int(factor * h)
        self._filter('scale={}:{}'.format(w, h), **kwargs)
        self.working_size = w, h

    def crop(self, whxy, **kwargs):
        self._filter('crop={}:{}:{}:{}'.format(*whxy), **kwargs)
        self.working_size = whxy[0], whxy[1]

    def rotate(self, degrees, **kwargs):
        self._filter('rotate={}'.format(degrees), **kwargs)

    def poster(self, bbox, path):
        W, H = bbox
        w, h = self.working_size
        factor = min(W / w, H / h)
        size = '{}x{}'.format(int(factor * w), int(factor * h))
        cmd = ['ffmpeg', '-i', self.working_path, '-s', size, '-vframes', '1', path]
        logging.debug('%s: running ffmpeg\n%s', self.path, ' '.join(cmd))
        subprocess.check_output(cmd, stderr=subprocess.PIPE)

    def thumbnail(self, size, path):
        srcw, srch = self.working_size
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
            width, height = self.working_size
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
            return int(args[0]), int(args[1])
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

    def make_thumbnails(self,
                        base=None,
                        sizes=(('full', 600), ('thumb', 100)),
                        replace=False,
                        fast=False):
        '''Create a small video and save a preview image to disk.'''
        base = base or os.path.dirname(db.DB)
        nailer = Thumbnailer(self.path, size=self.frame_size, fast=fast)
        for op in self.ops:
            nailer.apply_op(op)
        for name, size in sorted(sizes, key=lambda x: -x[1]):
            p = os.path.join(base, name, self.thumb_path)
            if os.path.exists(p) and not replace:
                continue
            dirname = os.path.dirname(p)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            if isinstance(size, int):
                size = (2 * size, size)
            if name == 'thumb':
                nailer.poster(size, p.replace(self.EXTENSION, 'jpg'))
            else:
                nailer.thumbnail(size, p)
