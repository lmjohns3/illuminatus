import click
import itertools
import math
import subprocess
import ujson


FILTER_ARGS = dict(
    rotate='degrees',
    brightness='percent',
    saturation='percent',
    hue='degrees',
    contrast='percent',
    autocontrast='percent',
    crop='x1 x2 y1 y2',
    hflip='',
    vflip='',
)

_DEBUG = 0


class Tool:
    '''A parent class for command-line tools to manipulate media files.'''

    def __init__(self, path, shape=None, filters=()):
        self.path = path
        self.shape = shape
        self._filters = []
        for kwargs in filters:
            self.apply_filter(**kwargs)
        self._already_run = False

    @property
    def input_args(self):
        return [self.path]

    @property
    def filter_args(self):
        return list(itertools.chain.from_iterable(f.split() for f in self._filters))

    def export(self, fmt, output):
        '''Run the tool to create an export output.

        Parameters
        ----------
        fmt : `Format`
            A `Format` class giving parameters for the output format.
        output : str
            Filename for the exported output.
        '''
        self._run(output)

    def _run(self, *output_args):
        '''Run this tool.

        Parameters
        ----------
        output_args : str
            Extra arguments to add to the command line for this tool.

        Returns
        -------
        The subprocess object that is running the command.
        '''
        cmd = list(self.BINARY)
        self._add_args(cmd, *output_args)
        if self._already_run:
            raise RuntimeError('Attempted to run twice: {!r}'.format(cmd))
        self._already_run = True
        if _DEBUG > 0:
            click.echo('{} {!r}'.format(click.style('$', fg='red'), cmd))
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _add_args(self, cmd, *output_args):
        '''Add arguments to a command to be run.'''
        cmd.extend(self.input_args)
        cmd.extend(self.filter_args)
        cmd.extend(output_args)

    def apply_filter(self, **kwargs):
        '''Apply a filter using this tool.

        Parameters
        ----------
        kwargs : dict
            A dictionary containing filter arguments. It must contain a
            "filter" key that names the filter to apply.
        '''
        if _DEBUG > 0:
            click.echo('Applying filter {!r}'.format(kwargs))
        flt = kwargs.pop('filter')
        if flt == 'rotate':
            angle = kwargs['degrees']
            w, h = self.shape
            self.filter_rotate(angle)
            if abs(angle % 90) > 0.1:
                self.filter_crop(*Tool._crop_after_rotate(w, h, angle))
        elif flt == 'crop':
            w, h = self.shape
            px1, py1 = kwargs['x1'], kwargs['y1']
            px2, py2 = kwargs['x2'], kwargs['y2']
            x1, y1 = int(w * px1), int(h * py1)
            x2, y2 = int(w * px2), int(h * py2)
            self.filter_crop(x2 - x1, y2 - y1, x1, y1)
        else:
            method = getattr(self, 'filter_{}'.format(flt))
            method(**kwargs)

    @staticmethod
    def _crop_after_rotate(width, height, degrees):
        '''Get the crop box that removes black triangles from a rotated photo.

        Suppose the original image has width w and height h.

        The width W and height H of the maximal crop box are given by:

            W: w * cos(t) + h * sin(t)
            H: w * sin(t) + h * cos(t)

        and the corners of the crop box are (counterclockwise from +x-axis):

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

        Parameters
        ----------
        width : int
            Width in pixels of original image before rotation.
        height : int
            Height in pixels of original image before rotation.
        degrees : float
            Degrees of rotation.

        Returns
        -------
        width : int
            Width of cropped region.
        height : int
            Height of cropped region.
        x : int
            Offset of left edge of cropped region from outer bounding box of
            rotated image.
        y : int
            Offset of top edge of cropped region from outer bounding box of
            rotated image.
        '''
        angle = math.radians(degrees)
        C = abs(math.cos(angle))
        S = abs(math.sin(angle))
        W = width * C + height * S
        H = width * S + height * C
        f = C * S / (S * S - C * C)
        a = f * (width * S - height * C)
        b = f * (height * S - width * C)
        return [int(W - 2 * a), int(H - 2 * b), int(a), int(b)]


class Ffmpeg(Tool):
    '''Ffmpeg is a tool for manipulating video files.'''

    BINARY = ('ffmpeg', )

    @property
    def input_args(self):
        return ['-i', self.path]

    @property
    def filter_args(self):
        return ['-vf', ','.join(self._filters)]

    def filter_autocontrast(self, percent):
        self._filters.append('histeq=strength={}'.format(percent / 100))

    def filter_saturation(self, percent):
        self._filters.append('hue=s={}'.format(percent / 100))

    def filter_brightness(self, percent):
        self._filters.append('hue=b={}'.format(percent / 100 - 1))

    def filter_hue(self, degrees):
        self._filters.append('hue=h={}'.format(degrees))

    def filter_scale(self, factor):
        w, h = self.shape
        w = int(factor * w)
        w -= w % 2
        h = int(factor * h)
        h -= h % 2
        self._set_bbox(w, h)
        self.shape = w, h

    def filter_crop(self, w, h, x, y):
        self._filters.append('crop={}:{}:{}:{}'.format(w, h, x, y))
        self.shape = w, h

    def filter_rotate(self, degrees):
        r = math.radians(degrees)
        self._filters.append('rotate={0}:ow=rotw({0}):oh=roth({0})'.format(r))

    def filter_hflip(self):
        self._filters.append('hflip')

    def filter_vflip(self):
        self._filters.append('vflip')

    def filter_fps(self, fps):
        self._filters.append('fps={}'.format(fps))

    def _set_bbox(self, w, h):
        flt = 'scale={}:{}:force_original_aspect_ratio=decrease:flags=lanczos'
        self._filters.append(flt.format(w, h))

    def export(self, fmt, output):
        self._set_bbox(*fmt.bbox)

        if fmt.fps is not None:
            self.filter_fps(fmt.fps)

        args = []

        if output.lower().endswith('.gif'):
            pal = 'split[x][z];[z]palettegen={}[y];[x][y]paletteuse'
            self._filters.append(pal.format(fmt.palette))
            self._filters.append('loop=0')

        elif output.lower().endswith('.jpg'):
            self._filters.append('thumbnail')
            args.extend(['-frames:v', '1'])

        else:
            if fmt.vcodec:
                args.extend(['-c:v', str(fmt.vcodec), '-crf', str(fmt.crf),
                             '-preset', str(fmt.preset), '-pix_fmt', 'yuv420p',
                             '-movflags', '+faststart'])
            else:
                args.append('-vn')
            if fmt.acodec:
                args.extend(['-c:a', str(fmt.acodec), '-b:a', str(fmt.abitrate)])
            else:
                args.append('-an')

        args.append(output)
        return self._run(*args)


class Convert(Tool):
    '''GraphicsMagick (or ImageMagick) is a tool for manipulating images.'''

    BINARY = ('gm', 'convert')

    @property
    def input_args(self):
        return [self.path, '-auto-orient']

    def filter_autocontrast(self, percent):
        self._filters.append(
            '-set histogram-threshold {} -normalize'.format(percent))

    def filter_contrast(self, percent):
        if percent < 100:
            self._filters.append('+contrast')
        if percent > 100:
            self._filters.append('-contrast')

    def filter_brightness(self, percent):
        self._filters.append('-modulate {},100,100'.format(percent))

    def filter_saturation(self, percent):
        self._filters.append('-modulate 100,{},100'.format(percent))

    def filter_hue(self, degrees):
        while degrees < 0:
            degrees += 360
        if degrees > 180:
            # map 181 degrees to -179, 270 to -90, etc.
            degrees -= 360
        self._filters.append('-modulate 100,100,{}'.format(degrees / 180))

    def filter_hflip(self):
        self._filters.append('-flop')

    def filter_vflip(self):
        self._filters.append('-flip')

    def filter_crop(self, w, h, x, y):
        self._filters.append('-crop {}x{}+{}+{}'.format(w, h, x, y))
        self.shape = w, h

    def filter_scale(self, factor):
        w, h = self.shape
        w = int(factor * w)
        w -= w % 2
        h = int(factor * h)
        h -= h % 2
        self._filters.append('-scale {}x{}'.format(w, h))
        self.shape = w, h

    def filter_rotate(self, degrees):
        self._filters.append('-rotate {}'.format(degrees))

    def export(self, fmt, output):
        wi, hi = self.shape
        wo, ho = fmt.bbox
        if wo < wi / 2 and ho < hi / 2:
            prescale = '-scale {}x{}'.format(int(1.2 * wo), int(1.2 * ho))
            self._filters.insert(0, prescale)
        self._filters.append('+profile *')
        self._filters.append('-thumbnail {}x{}'.format(wo, ho))
        self._run(output)


class Exiftool(Tool):
    '''Exiftool is used to extract metadata from images and videos.'''

    BINARY = ('exiftool', '-json', '-d', '%Y-%m-%d %H:%M:%S')

    def parse(self):
        output = self._run().stdout.decode('utf-8').strip()
        return ujson.loads(output)[0] if output.startswith('[{') else {}


class Sox(Tool):
    '''Sox is a tool for manipulating sound files.'''

    BINARY = ('sox', )

    def filter_crop(self, offset, length):
        self._filters.append('trim {} {}'.format(offset, length))

    def _add_args(self, cmd, *output_args):
        cmd.extend(self.input_args)
        cmd.extend(output_args)
        cmd.extend(self.filter_args)
