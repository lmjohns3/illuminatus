import climate
import io
import math
import os
import subprocess

from . import base
from . import db
from . import util

logging = climate.get_logger(__name__)


class Photo(base.Media):
    EXTENSION = 'jpg'
    MIME_TYPES = ('image/*', )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exif = None

    @property
    def exif(self):
        if self._exif is None:
            self._exif = tools.Exiftool(self.source_path).parse()
        return self._exif

    def build_exif_tags(self):
        '''Given an exif data structure, extract a set of tags.'''
        if not self.exif:
            return set()

        highest = util.round_to_highest_digits

        tags = set()

        if 'Model' in self.exif:
            t = self.exif['Model'].lower()
            for s in 'canon nikon kodak digital camera super powershot ed$ is$'.split():
                t = re.sub(s, '', t).strip()
            if t:
                tags.add(dict(tag='kit:{}'.format(t).lower(), type='exif'))

        if 'FNumber' in self.exif:
            t = 'f/{}'.format(round(2 * float(self.exif['FNumber'])) / 2)
            tags.add(t.replace('.0', ''))

        iso = self.exif.get('ISO')
        if iso:
            iso = int(self.exif['ISO'])
            tags.add('iso:{}'.format(highest(iso, 1 + int(iso > 1000))))

        if 'ShutterSpeed' in self.exif:
            s = self.exif['ShutterSpeed']
            n = -1
            if isinstance(s, (float, int)):
                n = int(1000 * s)
            elif s.startswith('1/'):
                n = int(1000. / float(s[2:]))
            else:
                raise ValueError('cannot parse ShutterSpeed "{}"'.format(s))
            tags.add('{}ms'.format(max(1, highest(n))))

        if 'FocalLength' in self.exif:
            tags.add('{}mm'.format(highest(self.exif['FocalLength'][:-2])))

        return set(dict(tag=t.strip().lower(), type='meta')
                   for t in tags if t.strip())

    def _prepare_image(self, fast=None):
        '''Get an image for this photo.'''
        img = PIL.Image.open(self.source_path)
        w, h = img.size
        if fast and (h > fast or w > fast):
            img.thumbnail((fast, fast), resample=PIL.Image.NEAREST)
        orient = self.exif.get('Orientation')
        if orient == 'Rotate 90 CW':
            img = img.rotate(-90)
        if orient == 'Rotate 180':
            img = img.rotate(-180)
        if orient == 'Rotate 270 CW':
            img = img.rotate(-270)
        for op in self.ops:
            img = self._apply_op(img, op)
        return img

    def make_thumbnails(self, full_size=800, thumb_size=80, base=None):
        '''Create thumbnails of this photo and save them to disk.

        Parameters
        ----------
        full_size : int, optional
            Size in pixels of the "full-size" thumbnail of the photo. This is
            typically shown in the photo editor view of the UI. Defaults to 500.
        thumb_size : int, optional
            Size in pixels of the thumbnail of the photo. This is typically
            shown in the photo browser view of the UI. Defaults to 100.
        base : str, optional
            If provided, store full-size and thumbnail images rooted at this
            path. Defaults to the location of the media database.
        '''
        img = self._prepare_image(1.2 * full_size)
        base = base or os.path.dirname(db.DB)
        for name, size in (('full', full_size), ('thumb', thumb_size)):
            img.thumbnail((size, size), resample=PIL.Image.ANTIALIAS)
            img.save(util.ensure_path(base, name, self.thumb_path))

    def serialize(self, size):
        '''Serialize this images as a string to the caller.

        Parameters
        ----------
        size : int or (int, int)
            If the size is a single integer, N, then images will be shrunk to
            fit inside an N x N box. If the size is given as two integers,
            (M, N), then images will be shrunk to fit inside an M x N box,
            applied to match the portrait/landscape orientation of the image.

        Returns
        -------
        image : str
            The image data, serialized to a byte string.
        '''
        img = self._prepare_image()
        if isinstance(size, int):
            w = h = size
        else:
            w, h = size
            if img.size[0] > img.size[1] and h > w:
                w, h = h, w
        img.thumbnail((w, h), resample=PIL.Image.ANTIALIAS)
        s = io.BytesIO()
        img.save(s, 'JPEG')
        return s.getvalue()
