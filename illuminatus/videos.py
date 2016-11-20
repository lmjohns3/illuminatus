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
            return self.exif[k + 'Width'], self.exif[k + 'Height']

        try:
            return ints(keys('Image'))
        except:
            pass
        try:
            return ints(keys('SourceImage'))
        except:
            pass
        try:
            return ints(self.exif['ImageSize'].split('x'))
        except:
            pass

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
