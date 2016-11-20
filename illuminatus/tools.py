import climate
import json
import math
import subprocess

logging = climate.get_logger(__name__)


class Command(list):
    '''A wrapper for invoking a subprocess.'''

    @property
    def binary(self):
        return self[0]

    @property
    def args(self):
        return self[1:]

    def start(self):
        '''Run this command as a subprocess.'''
        logging.info('%s', ' '.join(self))
        PIPE = subprocess.PIPE
        return subprocess.Popen(self, stdout=PIPE, stderr=PIPE)

    def run(self):
        '''Run this command as a subprocess, and wait for it to finish.'''
        logging.info('%s', ' '.join(self))
        PIPE = subprocess.PIPE
        proc = subprocess.Popen(self, stdout=PIPE, stderr=PIPE)
        proc.wait()
        return proc


class Tool(object):
    '''A parent class for command-line tools to manipulate media files.'''

    def __init__(self, path, shape):
        self.path = path
        self.shape = shape
        self._filters = []

    @property
    def filters(self):
        return self._filters

    @property
    def known_ops(self):
        return set(x.split('_')[1] for x in dir(self) if x.startswith('op_'))

    @property
    def input_args(self):
        return [self.path]

    def run(self, *args):
        cmd = Command(self.BINARY)
        cmd.extend(self.input_args)
        for filter in self.filters:
            cmd.extend(filter)
        cmd.extend(*args)
        return cmd.run()

    def apply_op(self, handle, op):
        if op['key'] not in self.known_ops:
            logging.info('%s: unknown op %r', self.path, op)
            return
        logging.info('%s: applying op %r', self.path, op)
        key = op['key']
        if key == 'autocontrast':
            self.op_autocontrast(op['cutoff'])
        if key == 'contrast':
            self.op_contrast(op['percent'])
        if key == 'brightness':
            self.op_brightness(op['percent'])
        if key == 'saturation':
            self.op_saturation(op['percent'])
        if key == 'hue':
            self.op_hue(op['percent'])
        if key == 'scale':
            self.op_scale(op['factor'])
        if key == 'rotate':
            w, h = self.shape
            self.op_rotate(op['degrees'])
            self.op_crop(Tool._crop_after_rotate(w, h, op['degrees']))
        if key == 'crop':
            w, h = self.shape
            px1, py1, px2, py2 = op['box']
            x1, y1 = int(w * px1), int(h * py1)
            x2, y2 = int(w * px2), int(h * py2)
            self.op_crop([x2 - x1, y2 - y1, x1, y1])

    def export(self, shape, path):
        self.scale(shape)
        return self.run(path)

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
        '''
        angle = math.radians(degrees)
        C = abs(math.cos(angle))
        S = abs(math.sin(angle))
        W = width * C + height * S
        H = width * S + height * C
        f = C * S / (S * S - C * C)
        a = f * (width * S - height * C)
        b = f * (height * S - width * C)
        return [int(a), int(b), int(W - a), int(H - b)]


class Ffmpeg(Tool):
    '''Ffmpeg is a tool for manipulating video files.'''

    BINARY = 'ffmpeg'

    def __init__(self, path, shape, crf=30):
        super().__init__(path, shape)
        self.crf = crf
        self._filters = []

    @property
    def input_args(self):
        audio = '-c:a libfaac -b:a 100k'
        video = '-c:v libx264 -pre ultrafast -crf {}'.format(self.crf)
        return ['-i', self.path] + audio.split() + video.split()

    @property
    def filters(self):
        return [f if isinstance(f, list) else ['-vf', f] for f in self._filters]

    def op_saturation(self, percent):
        self._filters.append('hue=s={}'.format(percent / 100))

    def op_brightness(self, percent):
        self._filters.append('hue=b={}'.format(percent / 100 - 1))

    def op_hue(self, percent):
        self._filters.append('hue=h={}'.format(percent * 180))

    def op_scale(self, factor):
        w, h = self.shape
        w = int(factor * w)
        w -= w % 2
        h = int(factor * h)
        h -= h % 2
        self._filters.append('scale={}:{}'.format(w, h))
        self.shape = w, h

    def op_crop(self, whxy):
        w, h, x, y = whxy
        self._filters.append('crop={}:{}:{}:{}'.format(w, h, x, y))
        self.shape = w, h

    def op_rotate(self, degrees):
        r = math.radians(degrees)
        self._filters.append('rotate={0}:ow=rotw({0}):oh=roth({0})'.format(r))

    def thumbnail(self, shape, path):
        w, h = self.shape
        self._filters.append('-s {}x{} -vframes 1'.format(w, h))
        return self.run(path)


class Convert(Tool):
    '''GraphicsMagick (or ImageMagick) is a tool for manipulating images.'''

    BINARY = 'convert'

    @property
    def filters(self):
        return [f.split() for f in self._filters]

    def op_autocontrast(self, cutoff):
        self._filters.append(
            '-set histogram-threshold {} -normalize'.format(cutoff))

    def op_contrast(self, percent):
        if percent < 100:
            self._filters.append('-contrast')
        if percent > 100:
            self._filters.append('+contrast')

    def op_brightness(self, percent):
        self._filters.append('-modulate {},100,100'.format(percent))

    def op_saturation(self, percent):
        self._filters.append('-modulate 100,{},100'.format(percent))

    def op_hue(self, percent):
        self._filters.append('-modulate 100,100,{}'.format(percent))

    def op_crop(self, whxy):
        w, h, x, y = whxy
        self._filters.append('-crop {}x{}+{}+{}'.format(w, h, x, y))
        self.shape = w, h

    def op_scale(self, factor):
        w, h = self.shape
        w = int(factor * w)
        w -= w % 2
        h = int(factor * h)
        h -= h % 2
        self._filters.append('-scale {}x{}'.format(w, h))
        self.shape = w, h

    def op_rotate(self, degrees):
        self._filters.append('-rotate {}'.format(degrees))

    def thumbnail(self, shape, path):
        self._filters.append('-thumbnail {}x{}'.format(*shape))
        return self.run(path)


class Exiftool(Tool):
    '''Exiftool is used to extract metadata from images and videos.'''

    BINARY = 'exiftool'

    @property
    def input_args(self):
        return ['-json', self.path]

    def parse(self):
        return json.loads(self.run().stdout)


class Sox(Tool):
    '''Sox is a tool for manipulating sound files.'''

    BINARY = 'sox'
