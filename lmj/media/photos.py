import climate
import math
import os
import PIL.Image
import PIL.ImageOps

from . import base
from . import db
from . import util

logging = climate.get_logger(__name__)


class Photo(base.Media):
    MEDIUM = 1
    MIME_TYPES = ('image/*', )

    @property
    def thumb_path(self):
        id = '%08x' % self.id
        return os.path.join(id[:-3], '%s.jpg' % id)

    def to_dict(self):
        return dict(
            id=self.id,
            medium=self.MEDIUM,
            path=self.path,
            stamp=self.stamp,
            thumb=self.thumb_path,
            ops=self.ops,
            dateTags=list(self.datetime_tag_set),
            userTags=list(self.user_tag_set),
            exifTags=list(self.exif_tag_set),
        )

    def read_exif_tags(self):
        '''Given an exif data structure, extract a set of tags.'''
        if not self.exif:
            return set()

        highest = util.round_to_highest_digits
        tags = super().read_exif_tags()

        if 'FNumber' in self.exif:
            t = 'f/{}'.format(round(2 * float(self.exif['FNumber'])) / 2)
            tags.add(t.replace('.0', ''))

        if 'ISO' in self.exif:
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

        return util.normalized_tag_set(tags)

    def make_thumbnails(self,
                        base=None,
                        sizes=(('full', 1000), ('thumb', 100)),
                        replace=False,
                        fast=False):
        '''Create thumbnails of this photo and save them to disk.'''
        base = base or os.path.dirname(db.DB)
        img = self.get_image(fast)
        for name, size in sorted(sizes, key=lambda x: -x[1]):
            p = os.path.join(base, name, self.thumb_path)
            if replace or not os.path.exists(p):
                dirname = os.path.dirname(p)
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                if isinstance(size, int):
                    size = (2 * size, size)
                img.thumbnail(size, PIL.Image.ANTIALIAS)
                img.save(p)

    def get_image(self, fast=False):
        img = PIL.Image.open(self.path)
        if fast:
            factor = 1000 / max(img.size)
            img = img.resize(
                (int(img.size[0] * factor), int(img.size[1] * factor)),
                resample=PIL.Image.BILINEAR)
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

    def rotate(self, degrees):
        if self.ops and self.ops[-1]['key'] == self.Ops.Rotate:
            op = self.ops.pop()
            degrees += op['degrees']
        self._add_op(self.Ops.Rotate, degrees=degrees % 360)

    def saturation(self, level):
        self._add_op(self.Ops.Saturation, level=level)

    def contrast(self, level):
        self._add_op(self.Ops.Contrast, level=level)

    def brightness(self, level):
        self._add_op(self.Ops.Brightness, level=level)

    def crop(self, box):
        self._add_op(self.Ops.Crop, box=box)

    def autocontrast(self):
        self._add_op(self.Ops.Autocontrast)

    def _add_op(self, key, **op):
        op['key'] = key
        self.ops.append(op)
        self.make_thumbnails(replace=True, fast=True)
        db.update(self)

    def _apply_op(self, img, op):
        logging.info('%s: applying op %r', self.path, op)
        key = op['key']
        if key == self.Ops.Autocontrast:
            # http://opencvpython.blogspot.com/2013/03/histograms-2-histogram-equalization.html
            return PIL.ImageOps.autocontrast(img, op.get('cutoff', 0.5))
        if key == self.Ops.Brightness:
            return PIL.ImageOps.brightness(img).enhance(op['level'])
        if key == self.Ops.Contrast:
            return PIL.ImageOps.contrast(img).enhance(op['level'])
        if key == self.Ops.Saturation:
            return PIL.ImageOps.color(img).enhance(op['level'])
        if key == self.Ops.Crop:
            x1, y1, x2, y2 = op['box']
            width, height = img.size
            x1 = int(width * x1)
            y1 = int(height * y1)
            x2 = int(width * x2)
            y2 = int(height * y2)
            return img.crop([x1, y1, x2, y2])
        if key == self.Ops.Rotate:
            w, h = img.size
            t = op['degrees']
            img = img.rotate(t, resample=PIL.Image.BICUBIC, expand=1)
            return img.crop(Photo._crop_after_rotate(w, h, math.radians(t)))
        logging.info('%s: unknown image op %r', self.path, op)
        return img
        # TODO: apply more image transforms

    @staticmethod
    def _crop_after_rotate(width, height, angle):
        '''Get the crop box that removes black triangles from a rotated photo.

            W: w * cos(t) + h * sin(t)
            H: w * sin(t) + h * cos(t)

            A: (h * sin(t), 0)
            B: (0, h * cos(t))
            C: (W - h * sin(t), H)
            D: (W, H - h * cos(t))

            AB:  y = h * cos(t) - x * cos(t) / sin(t)
            DA:  y = (x - h * sin(t)) * (H - h * cos(t)) / (W - h * sin(t))

        I used sympy to solve the equations for lines AB (evaluated at point
        (a, b) on that line) and DA (evaluated at point (W - a, b)):

            b = h * cos(t) - a * cos(t) / sin(t)
            b = (W - a - h * sin(t)) * (H - h * cos(t)) / (W - h * sin(t))

        The solution is given as:

            a = f * (w * sin(t) - h * cos(t))
            b = f * (h * sin(t) - w * cos(t))
            f = sin(t) * cos(t) / (sin(t)**2 - cos(t)**2)
        '''
        C = abs(math.cos(angle))
        S = abs(math.sin(angle))
        W = width * C + height * S
        H = width * S + height * C
        f = C * S / (S * S - C * C)
        a = f * (width * S - height * C)
        b = f * (height * S - width * C)
        return [int(a), int(b), int(W - a), int(H - b)]

    @staticmethod
    def create(path, tags, add_path_tags=0):
        '''Create a new Photo from the file at the given path.'''
        photo = db.insert(path, Photo.MEDIUM)

        stamp = util.compute_timestamp_from_exif(photo.exif)
        tags = set(tags) + set(util.get_path_tags(path, add_path_tags))

        photo.meta = dict(
            stamp=stamp,
            thumb=photo.thumb_path,
            userTags=list(sorted(util.normalized_tag_set(tags))),
            exifTags=list(sorted(photo.read_exif_tags())))

        photo.make_thumbnails()

        db.update(photo)

        logging.info('user: %s; exif: %s',
                     ', '.join(photo.meta['userTags']),
                     ', '.join(photo.meta['exifTags']),
                     )

    def cleanup(self):
        '''Remove thumbnails of this photo.'''
        base = os.path.dirname(db.DB)
        for size in os.listdir(base):
            try:
                os.unlink(os.path.join(base, size, self.thumb_path))
            except:
                pass

    def export(self, target, sizes=(('full', 1000), ('thumb', 100)), replace=False):
        '''Export this photo by saving thumbnails of specific sizes.'''
        self.make_thumbnails(target, sizes=sizes, replace=replace)
