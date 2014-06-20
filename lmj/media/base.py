import climate
import datetime
import re
import subprocess

from . import util

logging = climate.get_logger(__name__)


class Media:
    class Ops:
        Autocontrast = 'autocontrast'
        Brightness = 'brightness'
        Contrast = 'contrast'
        Crop = 'crop'
        Rotate = 'rotate'
        Saturation = 'saturation'

    def __init__(self, id=-1, path='', meta=None):
        self.id = id
        self.path = path
        self.meta = util.parse(meta or '{}')
        self._exif = None

    @property
    def ops(self):
        return self.meta.setdefault('ops', [])

    @property
    def exif(self):
        if self._exif is None:
            self._exif, = util.parse(subprocess.check_output(
                    ['exiftool', '-charset', 'UTF8', '-json', self.path]
            ).decode('utf-8'))
        return self._exif

    @property
    def tag_set(self):
        return self.datetime_tag_set | self.user_tag_set | self.exif_tag_set

    @property
    def user_tag_set(self):
        return util.normalized_tag_set(self.meta.get('userTags'))

    @property
    def exif_tag_set(self):
        return util.normalized_tag_set(self.meta.get('exifTags'))

    @property
    def datetime_tag_set(self):
        if not self.stamp:
            return set()

        def ordinal(n):
            s = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
            if 10 < n < 20: s = 'th'
            return '%d%s' % (n, s)

        # for computing the hour tag, we set the hour boundary at 48-past, so
        # that any time from, e.g., 10:48 to 11:47 gets tagged as "11am"
        hour = self.stamp + datetime.timedelta(minutes=12)

        return util.normalized_tag_set(
            [self.stamp.strftime('%Y'),                # 2009
             self.stamp.strftime('%B'),                # january
             self.stamp.strftime('%A'),                # monday
             ordinal(int(self.stamp.strftime('%d'))),  # 22nd
             hour.strftime('%I%p').strip('0'),         # 4pm
             ])

    @property
    def stamp(self):
        stamp = self.meta.get('stamp')
        if not stamp:
            return None
        if isinstance(stamp, datetime.datetime):
            return stamp
        return datetime.datetime.strptime(stamp[:19], '%Y-%m-%dT%H:%M:%S')

    def read_exif_tags(self):
        if not self.exif:
            return set()

        tags = set()

        if 'Model' in self.exif:
            t = self.exif['Model'].lower()
            for s in 'canon nikon kodak digital camera super powershot ed$ is$'.split():
                t = re.sub(s, '', t).strip()
            if t:
                tags.add('kit:{}'.format(t))

        return tags
