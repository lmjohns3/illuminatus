import arrow
import enum
import mimetypes
import os
import re

# Names of camera models, these will be filtered out of the metadata tags.
_CAMERA_WORD_BLACKLIST = 'canon nikon kodak digital camera super powershot'.split()

# EXIF tags where we should look for timestamps.
_TIMESTAMP_KEYS = 'DateTimeOriginal CreateDate ModifyDate FileModifyDate'.split()
_TIMESTAMP_FORMATS = ['YYYY-MM-DD HH:mm:ss', 'YYYY:MM:DD HH:mm:ss']

# Pattern for matching a floating-point number.
_FLOAT_PATTERN = r'(\d+)(\.\d+)?'

# Pattern for matching a geotagging coordinate.
_GEO_PATTERN = r'(?P<deg>\d+) deg (?P<min>\d+)\' (?P<sec>\d+(\.\d*)?)" (?P<sgn>[{}])'


@enum.unique
class Medium(enum.Enum):
    '''Enumeration of different supported media types.'''
    Audio = 1
    Photo = 2
    Video = 3


def medium_for(path):
    '''Determine the appropriate medium for a given path.

    Parameters
    ----------
    path : str
        Filesystem path where the asset is stored.

    Returns
    -------
    A string naming an asset medium. Returns None if no known media types
    handle the given path.
    '''
    mime, _ = mimetypes.guess_type(path)
    for pattern, medium in (('audio/.*', Medium.Audio),
                            ('video/.*', Medium.Video),
                            ('image/.*', Medium.Photo)):
        if re.match(pattern, mime):
            return medium
    return None


class Format:
    '''A POD class representing an export file format specification.

    Attributes
    ----------
    extension : str
        Filename extension.
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
        Number of colors in the palette for exported animated GIFs.
    vcodec : str
        Codec to use for exported video.
    acodec : str
        Name of an audio codec to use when exporting videos. If None, remove
        audio from exported videos.
    abitrate : str
        Bitrate specification for audio in exported videos. If None, remove
        audio from exported videos.
    crf : int
        Quality scale for exporting videos.
    preset : str
        Speed preset for exporting videos.
    '''

    def __init__(self, ext=None, bbox=None, fps=None, channels=1, palette=255,
                 acodec='aac', abitrate='128k', vcodec='libx264', crf=30,
                 preset='medium'):
        self.ext = ext
        self.bbox = bbox
        if isinstance(bbox, int):
            self.bbox = (bbox, bbox)
        self.fps = fps
        self.channels = channels
        self.acodec = acodec
        self.abitrate = abitrate
        self.palette = palette
        self.vcodec = vcodec
        self.crf = crf
        self.preset = preset

    def __str__(self):
        parts = []
        if self.ext is not None:
            parts.append(self.ext)
        if self.bbox is not None:
            parts.append('{}x{}'.format(*self.bbox))
        if self.fps:
            parts.append('fps={}'.format(self.fps))
        for key, default in (('channels', 1),
                             ('palette', 255),
                             ('acodec', 'aac'),
                             ('abitrate', '128k'),
                             ('vcodec', 'libx264'),
                             ('crf', 30),
                             ('preset', 'medium')):
            value = getattr(self, key)
            if value != default:
                parts.append('{}={}'.format(key, value))
        return ','.join(parts)

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
            if '=' in item:
                key, value = item.split('=', 1)
            elif re.match(r'\d+(x\d+)?', item):
                key, value = 'bbox', item
            else:
                key, value = 'ext', item
            if key == 'bbox':
                if 'x' in value:
                    w, h = value.split('x')
                    value = (int(w), int(h))
                else:
                    value = (int(value), int(value))
            if hasattr(value, 'isdigit') and value.isdigit():
                value = int(value)
            kwargs[key] = value
        return cls(**kwargs)


def get_timestamp(path, meta):
    '''Get the timestamp for an asset based on metadata or file mtime.

    Parameters
    ----------
    path : str
        File path for the asset.
    meta : dict
        Metadata values for the asset

    Returns
    -------
    An `arrow` datetime object.
    '''
    if meta:
        for key in _TIMESTAMP_KEYS:
            stamp = meta.get(key)
            if stamp is not None:
                try:
                    return arrow.get(stamp, _TIMESTAMP_FORMATS)
                except ValueError:
                    pass
    try:
        return arrow.get(os.path.getmtime(path))
    except FileNotFoundError:
        pass
    return arrow.get('1000-01-01 00:00:00')


def get_width(meta):
    '''Get the width of a media asset, in pixels.

    Parameters
    ----------
    meta : dict
        A dictionary mapping metadata fields to values.

    Returns
    -------
    A width value in pixels. Returns -1 if no value can be found.
    '''
    for key in ('ImageWidth', 'SourceImageWidth'):
        if key in meta:
            return int(meta[key])
    if 'ImageSize' in meta:
        return int(meta['ImageSize'].split('x')[0])
    return -1


def get_height(meta):
    '''Get the height of a media asset, in pixels.

    Parameters
    ----------
    meta : dict
        A dictionary mapping metadata fields to values.

    Returns
    -------
    A height value in pixels. Returns -1 if no value can be found.
    '''
    for key in ('ImageHeight', 'SourceImageHeight'):
        if key in meta:
            return int(meta[key])
    if 'ImageSize' in meta:
        return int(meta['ImageSize'].split('x')[1])
    return -1


def get_duration(meta):
    '''Get the duration of a media asset, in seconds.

    Parameters
    ----------
    meta : dict
        A dictionary mapping metadata fields to values.

    Returns
    -------
    A duration value in seconds. Returns -1 if no value can be found.
    '''
    value = meta.get('Duration', '')
    if re.match(r'^[:\d]+$', value):
        sec, mul = 0, 1
        for n in reversed(value.split(':')):
            sec += mul * int(n)
            mul *= 60
        return sec
    if re.match(r'^[.\d]+ s$', value):
        return int(round(float(value.split()[0])))
    return -1


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


def get_latitude(meta):
    '''Compute the latitude of an asset from exif metadata.

    Parameters
    ----------
    meta : dict
        A dictionary mapping metadata fields to values.

    Returns
    -------
    A latitude value, as a floating point number of degrees from the equator.
    If the geo information cannot be computed this will return None.
    '''
    pattern = _GEO_PATTERN.format('NS')
    lat = _geo_to_degrees(meta.get('GPSLatitude', ''), pattern, 'N')
    if lat is None:
        lat = _geo_to_degrees(meta.get('GPSPosition', ''), pattern, 'N')
    return lat


def get_longitude(meta):
    '''Compute the longitude of an asset from exif metadata.

    Parameters
    ----------
    meta : dict
        A dictionary mapping metadata fields to values.

    Returns
    -------
    A longitude value, as a floating point number of degrees from the meridian
    line. If the geo information cannot be computed this will return None.
    '''
    pattern = _GEO_PATTERN.format('EW')
    lng = _geo_to_degrees(meta.get('GPSLongitude', ''), pattern, 'E')
    if lng is None:
        lng = _geo_to_degrees(meta.get('GPSPosition', ''), pattern, 'E')
    return lng


def _round_to_most_significant_digits(n, digits=1):
    '''Return n rounded to the most significant `digits` digits.'''
    nint = n
    if isinstance(nint, float):
        nint = int(nint)
    if not isinstance(nint, int):
        match = re.match(r'^(\d+).*$', n)
        if match:
            nint = int(match.group(1))
        else:
            raise ValueError(n)
    if nint < 10 ** digits:
        return nint
    shift = 10 ** (len(str(n)) - digits)
    return int(shift * round(nint / shift))


def gen_metadata_tags(meta):
    '''Generate a set of metadata tags.

    Parameters
    ----------
    meta : dict
        A dictionary mapping metadata fields to values.

    Yields
    ------
    A :class:`Tag`s derived from the given metadata.
    '''
    if not meta:
        return

    highest = _round_to_most_significant_digits

    model = meta.get('CameraModelName', meta.get('Model', '')).lower()
    for pattern in _CAMERA_WORD_BLACKLIST + ['ed$', 'is$']:
        model = re.sub(pattern, '', model).strip()
    if model:
        yield 'kit:{}'.format(model).lower()

    fstop = meta.get('FNumber', '')
    if isinstance(fstop, (int, float)) or re.match(_FLOAT_PATTERN, fstop):
        yield 'f/{}'.format(round(10 * float(fstop)) / 10)

    mm = meta.get('FocalLengthIn35mmFormat', meta.get('FocalLength', ''))
    if isinstance(mm, str):
        match = re.match(_FLOAT_PATTERN + r'\s*mm', mm)
        mm = match.group(1) if match else None
    if mm:
        yield '{}mm'.format(highest(mm))


def gen_datetime_tags(stamp):
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
