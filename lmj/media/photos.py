import cv2
import cv2.cv
import datetime
import lmj.cli
import os
import PIL.Image
import PIL.ImageOps
import re
import subprocess

from . import db
from . import util

logging = lmj.cli.get_logger(__name__)


class Photo(object):
    MEDIUM = 1
    MIME_TYPES = ('image/.*', )

    def __init__(self, id=-1, path='', meta=None):
        self.id = id
        self.path = path
        self.meta = util.parse(meta or '{}')
        self._exif = None

    @property
    def ops(self):
        return self.meta.get('ops', [])

    @property
    def exif(self):
        if self._exif is None:
            self._exif, = util.parse(subprocess.check_output(
                    ['exiftool', '-json', self.path]))
        return self._exif

    @property
    def tag_set(self):
        return self.datetime_tag_set | self.user_tag_set | self.exif_tag_set

    @property
    def user_tag_set(self):
        return util.normalized_tag_set(self.meta.get('user_tags'))

    @property
    def exif_tag_set(self):
        return util.normalized_tag_set(self.meta.get('exif_tags'))

    @property
    def datetime_tag_set(self):
        if not self.stamp:
            return set()

        def ordinal(n):
            s = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
            if 10 < n < 20: s = 'th'
            return '%d%s' % (n, s)

        return util.normalized_tag_set(
            [self.stamp.strftime('%Y'),
             self.stamp.strftime('%B'),
             self.stamp.strftime('%A'),
             ordinal(int(self.stamp.strftime('%d'))),
             self.stamp.strftime('%I%p').strip('0'),
             ])

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
        return os.path.join(id[:-3], '%s.jpg' % id)

    def to_dict(self):
        return dict(id=self.id,
                    path=self.path,
                    stamp=self.stamp,
                    meta=self.meta,
                    thumb=self.thumb_path,
                    tags=list(self.tag_set))

    def read_exif_tags(self):
        '''Given an exif data structure, extract a set of tags.'''
        if not self.exif:
            return []

        def highest(n, digits=1):
            '''Return n rounded to the top `digits` digits.'''
            n = float(n)
            if n < 10 ** digits:
                return int(n)
            shift = 10 ** (len(str(int(n))) - digits)
            return int(shift * round(n / shift))

        tags = set()

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

        if 'Model' in self.exif:
            t = self.exif['Model'].lower()
            for s in 'canon nikon kodak digital camera super powershot ed$ is$'.split():
                t = re.sub(s, '', t).strip()
            if t:
                tags.add('kit:{}'.format(t))

        return util.normalized_tag_set(tags)

    def make_thumbnails(self,
                        base=os.path.dirname(db.DB),
                        sizes=(('full', 1000), ('thumb', 100)),
                        replace=False):
        '''Create thumbnails of this photo and save them to disk.'''
        img = self.get_image()
        for name, size in sorted(sizes, key=lambda x: -x[1]):
            p = os.path.join(base, name, self.thumb_path)
            dirname = os.path.dirname(p)
            try: os.makedirs(dirname)
            except: pass
            if replace or not os.path.exists(p):
                if isinstance(size, int):
                    size = (2 * size, size)
                img.thumbnail(size, PIL.Image.ANTIALIAS)
                img.save(p)

    # from https://gist.github.com/npinto/3632388
    def detect_faces(self,
                     cascade='haarcascades/haarcascade_frontalface_alt.xml',
                     scale=1.3,
                     min_neighbors=4,
                     min_size=(20, 20),
                     flags=cv2.cv.CV_HAAR_SCALE_IMAGE):
        rects = cv2.CascadeClassifier(cascade).detectMultiScale(
            self.get_image().convert('L'),
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=min_size,
            flags=flags)
        return rects[:, 2:] + rects[:, :2] if rects else []

    def get_image(self):
        img = PIL.Image.open(self.path)
        orient = self.exif.get('Orientation')
        if orient == 'Rotate 90 CW':
            img = img.rotate(-90)
        if orient == 'Rotate 180':
            img = img.rotate(-180)
        if orient == 'Rotate 270 CW':
            img = img.rotate(-270)

        for op in self.ops:
            key = op['key']
            if key == 'normalize':
                # http://opencvpython.blogspot.com/2013/03/histograms-2-histogram-equalization.html
                img = PIL.ImageOps.autocontrast(img.convert('L'), op.get('cutoff', 0.5))
                continue
            if key == 'crop':
                x1, y1, x2, y2 = op['box']
                width, height = img.size
                x1 = int(width * x1)
                y1 = int(height * y1)
                x2 = int(width * x2)
                y2 = int(height * y2)
                img = img.crop([x1, y1, x2, y2])
                continue
            if key == 'rotate':
                img = img.rotate(op['degrees'])
                continue
            if key == 'contrast':
                img = img.point(op['gamma'], op['alpha'])
                continue
            # TODO: apply more image transforms

        return img

    def add_op(self, key, **op):
        op['key'] = key
        self.ops.append(op)
        self.update_thumbnail()
        db.update(self)

    def update_thumbnail(self):
        raise NotImplementedError

    @staticmethod
    def create(path, tags, add_path_tag=False):
        '''Create a new Photo from the file at the given path.'''
        def compute_timestamp_from(exif, key):
            raw = exif.get(key)
            if not raw:
                return None
            for fmt in ('%Y:%m:%d %H:%M:%S', '%Y:%m:%d %H:%M+%S'):
                try:
                    return datetime.datetime.strptime(raw[:19], fmt)
                except:
                    pass
            return None

        p = db.insert(path, Photo.MEDIUM)

        stamp = None
        for key in ('DateTimeOriginal', 'CreateDate', 'ModifyDate', 'FileModifyDate'):
            stamp = compute_timestamp_from(p.exif, key)
            if stamp:
                 break
        if stamp is None:
            stamp = datetime.datetime.now()

        tags = list(tags)
        if add_path_tag:
            tags.append(os.path.basename(os.path.dirname(path)))

        p.meta = dict(
            stamp=stamp,
            thumb=p.thumb_path,
            user_tags=sorted(util.normalized_tag_set(tags)),
            exif_tags=sorted(p.read_exif_tags()))

        logging.info('user: %s; exif: %s',
                     ', '.join(p.meta['user_tags']),
                     ', '.join(p.meta['exif_tags']),
                     )

        p.make_thumbnails()

        db.update(p)

    def cleanup(self):
        '''Remove thumbnails of this photo.'''
        base = os.path.dirname(db.DB)
        for size in os.listdir(base):
            try:
                os.unlink(os.path.join(base, size, self.thumb_path))
            except:
                pass

    def export(self, target, replace=False):
        '''Export this photo by saving thumbnails of specific sizes.'''
        self.make_thumbnails(target,
                             sizes=(('full', 1000), ('thumb', 100)),
                             replace=replace)
