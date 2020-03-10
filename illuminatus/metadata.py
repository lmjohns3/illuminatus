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

# Pattern for matching a geotagging coordinate.
_GEO_PATTERN = r'(?P<deg>\d+) deg (?P<min>\d+)\' (?P<sec>\d+(\.\d*)?)" (?P<sgn>[{}])'


def _geo_to_degrees(raw, axis):
    '''Convert a geo metadata field to float degrees.

    Parameters
    ----------
    raw : str
        Raw metadata string possibly containing a geo coordinate.
    axis : {'NS', 'EW'}
        Axis for values along one geo coordinate.

    Returns
    -------
    A floating point number of degrees, or None if nothing could be found.
    '''
    match = re.search(_GEO_PATTERN.format(axis), raw)
    if match is None:
        return None
    m = match.groupdict()
    deg = int(m['deg']) + int(m['min']) / 60 + float(m['sec']) / 3600
    return [-1, 1][m['sgn'] == axis[0]] * deg


class Metadata:
    '''A class holding metadata about an asset: timestamps, dimensions, etc.'''

    def __init__(self, path):
        proc = subprocess.run(
            ('exiftool', '-json', '-d', '%Y-%m-%d %H:%M:%S', path),
            encoding='utf-8', text=True, capture_output=True)
        self._data = json.loads(proc.stdout)[0]

    @property
    def stamp(self):
        '''Get the timestamp for an asset based on metadata or file mtime.

        Parameters
        ----------
        path : str
          File path for the asset.

        Returns
        -------
        An `arrow` datetime object.
        '''
        for key in _TIMESTAMP_KEYS:
            stamp = self._data.get(key)
            if stamp is not None:
                try:
                    return arrow.get(stamp, _TIMESTAMP_FORMATS)
                except ValueError:
                    pass

    @property
    def width(self):
        '''The width of a media asset, in pixels.'''
        for key in ('ImageWidth', 'SourceImageWidth'):
            if key in self._data:
                return int(self._data[key])
        if 'ImageSize' in self._data:
            return int(self._data['ImageSize'].split('x')[0])
        return -1

    @property
    def height(self):
        '''The height of a media asset, in pixels.'''
        for key in ('ImageHeight', 'SourceImageHeight'):
            if key in self._data:
                return int(self._data[key])
        if 'ImageSize' in self._data:
            return int(self._data['ImageSize'].split('x')[1])
        return -1

    @property
    def duration(self):
        '''The duration of a media asset, in seconds.'''
        value = self._data.get('Duration', '')
        if re.match(r'^[:\d]+$', value):
            sec, mul = 0, 1
            for n in reversed(value.split(':')):
                sec += mul * int(n)
                mul *= 60
            return sec
        if re.match(r'^[.\d]+ s$', value):
            return int(round(float(value.split()[0])))
        return -1

    @property
    def latitude(self):
        '''The latitude of an asset from exif metadata.'''
        lat = _geo_to_degrees(self._data.get('GPSLatitude', ''), 'NS')
        if lat is None:
            lat = _geo_to_degrees(self._data.get('GPSPosition', ''), 'NS')
        return lat

    @property
    def longitude(self):
        '''The longitude of an asset from exif metadata.'''
        lng = _geo_to_degrees(self._data.get('GPSLongitude', ''), 'EW')
        if lng is None:
            lng = _geo_to_degrees(self._data.get('GPSPosition', ''), 'EW')
        return lng

    @property
    def tags(self):
        '''Generator for metadata tags for an asset.'''
        model = self._data.get('CameraModelName', self._data.get('Model', '')).lower()
        for pattern in _CAMERA_WORD_BLACKLIST + [r'\bed$', r'\bis$']:
            model = re.sub(pattern, '', model).strip()
        model = re.sub(r"\W+", "-", model)
        if model:
            yield f'kit:{model}'

        fstop = self._data.get('FNumber', '')
        if isinstance(fstop, (int, float)) or re.match(r'(\d+)(\.\d+)?', fstop):
            yield f'ƒ-{int(float(fstop))}'

        mm = self._data.get('FocalLengthIn35mmFormat',
                            self._data.get('FocalLength', ''))
        if isinstance(mm, str):
            match = re.match(r'(\d+)(\.\d+)?\s*mm', mm)
            mm = match.group(1) if match else None
        if mm:
            # Round to 2 significant digits.
            yield f'{int(float("%.2g" % float(mm)))}mm'


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

    # for computing the hour tag, we set the hour boundary at 48-past, so
    # that any time from, e.g., 10:48 to 11:47 gets tagged as "11am"
    yield stamp.shift(minutes=12).format('ha').lower()
