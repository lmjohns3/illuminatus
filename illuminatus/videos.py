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

SCRATCH = 'illuminatus-scratch'

def mktemp():
    t = os.path.join(tempfile.gettempdir(), SCRATCH, uuid.uuid4().hex + '.mp4')
    if not os.path.isdir(os.path.dirname(t)):
        os.makedirs(os.path.dirname(t))
    return t


class Thumbnailer:
    def __init__(self, path, size, initial_size, crf=30):
        w, h = self.size = self.working_size = size
        self.path = path
        self.working_path = mktemp()
        os.symlink(path, self.working_path)
        self.audio = '-c:a libfaac -b:a 100k'.split()
        self.video = '-c:v libx264 -pre ultrafast -crf {}'.format(crf).split()
        self.filters = []
        self.scale(min(initial_size / w, initial_size / h))

    def __del__(self):
        if os.path.exists(self.working_path):
            if SCRATCH in self.working_path:
                os.unlink(self.working_path)

    def run(self, output):
        cmd = ['ffmpeg', '-i', self.working_path] + self.audio + self.video
        for vf in self.filters:
            cmd.append('-vf')
            cmd.extend(vf.split())
        cmd.append(output)
        logging.info('%s: running ffmpeg\n%s', self.path, ' '.join(cmd))
        subprocess.check_output(cmd, stderr=subprocess.PIPE)

    def saturation(self, level, **kwargs):
        self.filters.append('hue=b={}'.format(level - 1))

    def brightness(self, level, **kwargs):
        self.filters.append('hue=s={}'.format(level))

    def scale(self, factor, **kwargs):
        w, h = self.working_size
        w = int(factor * w)
        w -= w % 2
        h = int(factor * h)
        h -= h % 2
        self.filters.append('scale={}:{}'.format(w, h))
        self.working_size = w, h

    def crop(self, whxy, **kwargs):
        self.filters.append('crop={}:{}:{}:{}'.format(*whxy))
        self.working_size = whxy[0], whxy[1]

    def rotate(self, degrees, **kwargs):
        self.filters.append('rotate={}'.format(degrees))

    def poster(self, size, path):
        w, h = self.working_size
        if h > size or w > size:
            f = min(size / w, size / h)
            w, h = int(f * w), int(f * h)
        cmd = ['ffmpeg', '-i', self.working_path, '-s', '{}x{}'.format(w, h), '-vframes', '1', path]
        logging.info('%s: running ffmpeg\n%s', self.path, ' '.join(cmd))
        subprocess.check_output(cmd, stderr=subprocess.PIPE)

    def thumbnail(self, size, path):
        w, h = self.working_size
        if h > size or w > size:
            self.scale(min(size / w, size / h))
        self.run(path)

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
            return self.exif[k + 'Width'], self.exif[k + 'Height']
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
        tags = super().read_exif_tags()
        tags.add('video')
        return util.normalized_tag_set(tags)

    def make_thumbnails(self, full_size=800, thumb_size=80, base=None):
        '''Create a small video and save a preview image to disk.

        Parameters
        ----------
        full_size : int, optional
            Size in pixels of the small edge of the "full-size" thumbnail of the
            video. This is typically shown in the editor view of the UI.
            Defaults to 400.
        thumb_size : int, optional
            Size in pixels of the small edge of the poster image for the video.
            This is typically shown in the browser view of the UI. Defaults to
            100.
        base : str, optional
            If provided, store full-size and thumbnail images rooted at this
            path. Defaults to the location of the media database.
        '''
        nailer = Thumbnailer(self.path, self.frame_size, full_size)
        for op in self.ops:
            nailer.apply_op(op)

        # create "full" size video preview.
        base = base or os.path.dirname(db.DB)
        nailer.thumbnail(
            full_size, util.ensure_path(base, 'full', self.thumb_path))

        # create poster images at "full" and "thumb" size.
        pp = self.thumb_path.replace(self.EXTENSION, 'jpg')
        nailer.poster(full_size, os.path.join(base, 'full', pp))
        nailer.poster(thumb_size, os.path.join(base, 'thumb', pp))

    def serialize(self, size):
        '''Serialize this video to a byte string.

        Parameters
        ----------
        size : int or (int, int)
            If the size is a single integer, N, then the video will be shrunk to
            fit inside an N x N box. If the size is given as two integers,
            (M, N), then the video will be shrunk to fit inside an M x N box,
            applied to match the portrait/landscape orientation of the video.

        Returns
        -------
        video : str
            The video data, serialized to a byte string.
        '''
        nailer = Thumbnailer(self.path, self.frame_size, size, crf=23)
        for op in self.ops:
            nailer.apply_op(op)
        p = mktemp()
        nailer.thumbnail(size, p)
        buf = open(p, 'rb').read()
        os.unlink(p)
        return buf
