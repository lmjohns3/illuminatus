import arrow
import json
import os
import re
import subprocess

# Names of camera models, these will be filtered out of the metadata tags.
_CAMERA_WORD_BLACKLIST = (
    'canon fuji kodak nikon olympus samsung '
    'digital camera super powershot '
).split()

# EXIF tags where we should look for timestamps.
_TIMESTAMP_KEYS = 'DateTimeOriginal CreateDate ModifyDate FileModifyDate'.split()
_TIMESTAMP_FORMATS = ['YYYY-MM-DD HH:mm:ss', 'YYYY:MM:DD HH:mm:ss']

_EXIFTOOL = ('exiftool', '-n', '-json', '-d', '%Y-%m-%d %H:%M:%S')


class Metadata:
    '''A class holding metadata about an asset: timestamps, dimensions, etc.'''

    def __init__(self, path):
        proc = subprocess.run(
            _EXIFTOOL + (path, ), encoding='utf-8', text=True, capture_output=True)
        self._data = json.loads(proc.stdout)[0]

    @property
    def stamp(self):
        '''Creation timestamp for an asset, based on metadata or file mtime.'''
        for key in _TIMESTAMP_KEYS:
            try:
                return arrow.get(self._data[key], _TIMESTAMP_FORMATS)
            except (KeyError, ValueError) as _:
                pass

    @property
    def width(self):
        '''The width of an asset, in pixels.'''
        rot90 = int(self.orientation in (5, 6, 7, 8))
        return self._image_height_width[1 - rot90]

    @property
    def height(self):
        '''The height of an asset, in pixels.'''
        rot90 = int(self.orientation in (5, 6, 7, 8))
        return self._image_height_width[rot90]

    @property
    def _image_height_width(self):
        h = w = None
        for key in ('ImageHeight', 'SourceImageHeight'):
            h = self._data.get(key)
            if h:
                break
        for key in ('ImageWidth', 'SourceImageWidth'):
            w = self._data.get(key)
            if w:
                break
        if not h or not w and 'ImageSize' in self._data:
            h, w = tuple(int(z) for z in self._data['ImageSize'].split())
        return h, w

    @property
    def duration(self):
        '''Asset duration in seconds.'''
        return self._data.get('Duration')

    @property
    def orientation(self):
        return int(self._data.get('Orientation', 0))

    @property
    def audio_fps(self):
        return self._data.get('AudioSampleRate')

    @property
    def video_fps(self):
        return self._data.get('VideoFrameRate')

    @property
    def latitude(self):
        lat = self._data.get('GPSLatitude')
        if lat is not None:
            return lat
        latlng = self._data.get('GPSPosition')
        if latlng is not None:
            return float(latlng.split()[0])

    @property
    def longitude(self):
        lng = self._data.get('GPSLongitude')
        if lng is not None:
            return lng
        latlng = self._data.get('GPSPosition')
        if latlng is not None:
            return float(latlng.split()[1])

    @property
    def tags(self):
        '''Generator for metadata tags for an asset.'''
        model = self._data.get('CameraModelName', self._data.get('Model', '')).lower()
        for pattern in _CAMERA_WORD_BLACKLIST + [r'\bed$', r'\bis$']:
            model = re.sub(pattern, '', model).strip()
        model = re.sub(r"\W+", "-", model)
        if model:
            yield f'kit:{model}'

        fstop = self._data.get('FNumber')
        if fstop:
            yield f'ƒ-{int(float(fstop))}'

        for field in ('FocalLengthIn35mmFormat', 'FocalLength'):
            mm = self._data.get(field)
            if mm:
                # Round to 2 significant digits.
                yield f'{int(float("%.2g" % mm))}mm'
                break


def tags_from_stamp(stamp):
    '''Build a set of datetime tags.

    Parameters
    ----------
    stamp : `arrow.Arrow`
        Timestamp for constructing tags.

    Yields
    ------
    Tag strings derived from the timestamp.
    '''
    if not stamp:
        return

    # 2009
    yield stamp.format('YYYY')

    # january
    yield stamp.format('MMMM').lower()

    # 22nd
    yield stamp.format('Do').lower()

    # monday
    yield stamp.format('dddd').lower()

    # for computing the hour tag, we set the hour boundary (arbitrarily) at
    # 48-past, so that any time from, e.g., 10:48 to 11:47 gets tagged as "11am"
    yield stamp.shift(minutes=12).format('ha').lower()
