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


def load_config(path):
    thumbnails
    app.config['hide-originals'] = hide_originals
    fmts = app.config['formats'] = dict(audio=dict(small={}, large={}),
                                        photo=dict(small={}, large={}),
                                        video=dict(small={}, large={}))
    for medium in Medium:
        for size in ('small', 'large'):
            med = medium.name.lower()
            flag = kwargs.get(f'{size}_{med}_format', '')
            if flag:
                fmt = metadata.Format.parse(flag)
                fmts[size][med] = dict(path=str(fmt), ext=fmt.ext)


class Format:
    '''A class representing an export file format specification.

    Attributes
    ----------
    extension : str
        Filename extension, as well as the type of output file format.
    bbox : int
        Maximum size of the output. For photos and videos, exported frames must
        fit within a box of this size, while preserving the original aspect
        ratio.
    fps : str
        Frames per second when exporting audio or video. For videos this can
        be a rational number like "30/1.001" or a basic frame rate like "10".
    channels : int
        Number of channels in exported audio files.
    palette : int
        Number of colors in the palette for exporting animated GIFs.
    abr : int
        Audio bitrate specification in kilobits/sec for exported videos. If
        None, remove audio from exported videos.
    vbr : int
        Video bitrate specification in kilobits/sec for exported videos. If
        None, remove video from exported videos.
    '''

    DEFAULT_EXTENSIONS = {
        'audio': 'flac',
        'photo': 'png',
        'video': 'mp4',
    }

    def __init__(self, ext=None, bbox=None, fps=None, crf=None):
        self.ext = ext
        self.bbox = bbox
        if isinstance(bbox, int):
            self.bbox = (bbox, bbox)
        self.fps = fps
        self.crf = crf

    def __str__(self):
        parts = []
        if self.ext:
            parts.append(self.ext)
        if self.bbox:
            w, h = self.bbox
            parts.append(f'{w}x{h}')
        if self.fps:
            parts.append(f'{self.fps}fps')
        if self.crf:
            parts.append(f'crf{self.crf}')
        return ','.join(parts)

    def extension_for(self, medium):
        return self.ext or Format.DEFAULT_EXTENSIONS[medium.name.lower()]

    @classmethod
    def parse(cls, s):
        '''Parse a string s into a Format.

        The string is expected to consist of one or more parts, separated by
        commas. Each part can be:

          - A bare string matching MMM or MMMxNNN. This is used to specify a
            media geometry, giving the "bbox" property. If MMM is given, it
            designates a geometry of MMMxMMM.
          - A bare string. This is used to specify an output extension, which
            determines the encoding of the output.
          - A string with two halves containing one equals (=). The first half
            gives the name of a :class:`Format` field, while the second
            half gives the value for the field.

        Examples
        --------

        - 100: Use the default file format for the medium (JPG for photos and
               MP4 for movies), and size outputs to fit in a 100x100 box.
        - 100x100: Same as above.
        - bbox=100x100: Same.
        - png,100: Same as above, but use PNG for photo outputs.
        - ext=png,100: Same as above.
        - ext=png,bbox=100: Same as above.

        Parameters
        ----------
        s : str
            A string to parse.
        '''
        kwargs = {}
        for item in s.split(','):
            if re.match(r'\d+fps', item):
                kwargs['fps'] = int(item.replace('fps', ''))
            elif re.match(r'crf\d+', item):
                kwargs['crf'] = int(item.replace('crf', ''))
            elif re.match(r'\d+(x\d+)?', item):
                if 'x' in item:
                    w, h = item.split('x')
                    kwargs['bbox'] = (int(w), int(h))
                else:
                    kwargs['bbox'] = (int(item), int(item))
            else:
                kwargs['ext'] = item
        return cls(**kwargs)


def _geo_to_degrees(raw, pattern, positive):
    '''Convert a geo metadata field to float degrees.

    Parameters
    ----------
    raw : str
        Raw metadata string possibly containing a geo coordinate.
    pattern : str
        Regular expression pattern for finding geo coordinate fields.
    positive : str
        The compass direction that should be considered positive (N for
        latitude or E for longitude).

    Returns
    -------
    A floating point number of degrees, or None if nothing could be found.
    '''
    match = re.search(pattern, raw)
    if match is None:
        return None
    m = match.groupdict()
    deg = int(m['deg']) + int(m['min']) / 60 + float(m['sec']) / 3600
    return [-1, 1][m['sgn'] == positive] * deg


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
        pattern = _GEO_PATTERN.format('NS')
        lat = _geo_to_degrees(self._data.get('GPSLatitude', ''), pattern, 'N')
        if lat is None:
            lat = _geo_to_degrees(self._data.get('GPSPosition', ''), pattern, 'N')
        return lat

    @property
    def longitude(self):
        '''The longitude of an asset from exif metadata.'''
        pattern = _GEO_PATTERN.format('EW')
        lng = _geo_to_degrees(self._data.get('GPSLongitude', ''), pattern, 'E')
        if lng is None:
            lng = _geo_to_degrees(self._data.get('GPSPosition', ''), pattern, 'E')
        return lng

    @property
    def tags(self):
        '''Generator for metadata tags for an asset.'''
        model = self._data.get('CameraModelName', self._data.get('Model', '')).lower()
        for pattern in _CAMERA_WORD_BLACKLIST + [r'\bed$', r'\bis$']:
            model = re.sub(pattern, '', model).strip()
        model = re.sub(r"\W+", "-", model)
        if model:
            yield model

        fstop = self._data.get('FNumber', '')
        if isinstance(fstop, (int, float)) or re.match(r'(\d+)(\.\d+)?', fstop):
            yield f'f/{int(float(fstop))}'

        mm = self._data.get('FocalLengthIn35mmFormat',
                            self._data.get('FocalLength', ''))
        if isinstance(mm, str):
            match = re.match(r'(\d+)(\.\d+)?\s*mm', mm)
            mm = match.group(1) if match else None
        if mm:
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
