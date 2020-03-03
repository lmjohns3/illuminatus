import click
import contextlib
import itertools
import math
import os
import subprocess
import tempfile

_DEBUG = 0


def _run(*cmd):
    if _DEBUG > 0:
        click.echo(' '.join(cmd))
    return subprocess.run(cmd, capture_output=_DEBUG == 0)


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
    return int(W - 2 * a), int(H - 2 * b), int(a), int(b)


def _apply_filters(asset, runners):
    '''Apply a filter using this tool.

    Parameters
    ----------
    asset : :class:`Asset`
        Asset to use for media data.
    runners : dict
        A dictionary mapping strings to callables that implement different filters.
    '''
    w, h, t = asset.width, asset.height, asset.duration
    for kwargs in asset.filters:
        flt = kwargs.pop('filter')
        if flt == 'rotate':
            angle = kwargs['degrees']
            runners['rotate'](angle)
            if angle % 90 != 0:
                w, h, x, y = _crop_after_rotate(w, h, angle)
                runners['crop'](w, h, x, y)
        elif flt == 'crop':
            px1, py1 = kwargs['x1'], kwargs['y1']
            px2, py2 = kwargs['x2'], kwargs['y2']
            x1, y1 = int(w * px1), int(h * py1)
            x2, y2 = int(w * px2), int(h * py2)
            w, h = x2 - x1, y2 - y1
            runners['crop'](w, h, x1, y1)
        elif flt == 'scale':
            f = kwargs['factor']
            w = int(f * w)
            w -= w % 2
            h = int(f * h)
            h -= h % 2
            runners['scale'](w, h)
        elif flt == 'cut':
            start = kwargs.get('start', 0)
            duration = kwargs.get('duration', t - start)
            t -= duration
            runners['cut'](t, start, duration)
        else:
            runners[flt](**kwargs)


@contextlib.contextmanager
def _complex_filter(extracts, filters):
    for i, (start, duration) in enumerate(extracts):
        # https://superuser.com/questions/681885
        yield ','.join(f'[0:v]trim=0:{start}',
                       f'setpts=PTS-STARTPTS',
                       f'format=yuv420p[v{i}]')
        yield ','.join(f'[0:a]atrim=0:{start}', f'asetpts=PTS-STARTPTS[a{i}]')
        if start + duration < length:
            yield ','.join(f'[src_{n}:v]trim={start + duration}:{length}',
                           f'setpts=PTS-STARTPTS',
                           f'format=yuv420p[vid_{n}_2]')
            yield ','.join(f'[src_{n}:a]atrim={start + duration}:{length}',
                           f'asetpts=PTS-STARTPTS[aud_{n}_2]')
        if start > 0 and start + duration < length:
            yield f'[vid_{n}_1][aud_{n}_1][vid_{n}_2][aud_{n}_2]concat=n=2:v=1:a=1'

    if graph:
        with tempfile.NamedTemporaryFile(mode='w+') as script:
            for i, entry in enumerate(graph):
                if i:
                    script.write(';\n')
                script.write(entry)
            script.flush()
            yield script.name
    else:
        yield None


def ffmpeg(asset, fmt, output):
    '''Ffmpeg is a tool for manipulating audio and video files.

    Parameters
    ----------
    asset : :class:`Asset`
        Asset to use for media data.
    fmt : dict
        Formatting args for output.
    output : str
        Path for the output.
    '''
    # A list of extracted parts from the original video; these will be extracted
    # and concatenated (in the order in this list) before applying filters.
    extracts = []
    filters = []

    def scale(w, h):
        return f'scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos'

    def rotate(r):
        return f'rotate={r}:ow=rotw({r}):oh=roth({r})'

    def sigmoid(ratio):
        def curve(x):
            return (x ** ratio if x < 0.5 else
                    1 - curve(1 - x) if x > 0.5 else
                    0.5)
        return ' '.join(f'{x}/{curve(x)}' for x in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0))

    _apply_filters(asset, dict(
        autocontrast=lambda percent: filters.append(f'histeq=strength={percent / 100}'),
        brightness=lambda percent: filters.append(f'hue=b={percent / 100 - 1}'),
        contrast=lambda percent: filters.append(f"curves=m='{sigmoid(percent / 100)}'"),
        crop=lambda w, h, x, y: filters.append(f'crop={w}:{h}:{x}:{y}'),
        extract=lambda start, duration: extracts.append((start, duration)),
        fps=lambda fps: filters.append(f'fps={fps}'),
        hflip=lambda: filters.append('hflip'),
        hue=lambda degrees: filters.append(f'hue=h={degrees}'),
        rotate=lambda degrees: filters.append(rotate(math.radians(degrees))),
        saturation=lambda percent: filters.append(f'hue=s={percent / 100}'),
        scale=lambda w, h: filters.append(scale(w, h)),
        vflip=lambda: filters.append('vflip'),
    ))

    stem = os.path.splitext(output)[0]
    ext = fmt.extension_for(asset.medium)

    if asset.medium.name.lower() == 'photo':
        _run('ffmpeg', '-y', '-i', asset.path, '-vf', ','.join(filters), output)

    elif asset.medium.name.lower() == 'audio':
        if ext == 'png':
            # Make a spectrogram image of the middle 60 seconds.
            w, h = fmt.bbox
            t = asset.duration / 2
            start, end = max(0, t - 30), min(asset.duration, t + 30)
            trim = f'atrim={start}:{end}'
            spec = f'showspectrumpic=s={w}x{h}:color=viridis:scale=log:fscale=log'
            _run('ffmpeg', '-y', '-i', asset.path, '-af', f'{trim},{spec}', f'{stem}.png')

        else:
            with _complex_filter(extracts, filters) as script:
                _run('ffmpeg', '-y', '-i', asset.path, '-filter_complex_script', script,
                     '-ar', f'{fmt.ar or 44100}', '-f', ext, output)

    # asset.medium.name.lower() == 'video':
    elif ext == 'gif':
        w, h = fmt.bbox
        t = asset.duration / 2
        start, end = max(0, t - 5), min(asset.duration, t + 5)
        # Make a poster image from the middle of the video.
        _run('ffmpeg', '-y', '-i', asset.path, '-ss', f'{t}', '-an', '-vf', scale(w, h),
              '-frames:v', '1', f'{stem}.png')
        # Make an animated gif from the middle 10 seconds.
        _run('ffmpeg', '-y', '-i', asset.path, '-loop', '-1', '-an', '-vf', ';'.join([
            f'trim={start}:{end},fps={fmt.fps},{scale(w, h)},split[u][q]',
            '[u]fifo[v]', '[q]palettegen[p]', '[v][p]paletteuse',
        ]), f'{stem}.gif')

    elif ext == 'mp4':
        filters.append(scale(*fmt.bbox))
        if fmt.fps:
            filters.append(f'fps={fmt.fps}')
        with _complex_filter(extracts, filters) as script:
            # https://superuser.com/questions/1296374
            _run('ffmpeg', '-y', '-i', asset.path, '-filter_complex_script', script,
                 '-c:v', 'hevc_nvenc', '-level:v', '4.1', '-profile:v', 'main',
                 '-rc:v', 'vbr_hq', '-rc-lookahead:v', '32', '-refs:v', '16',
                 '-bf:v', '2', '-coder:v', 'cabac', '-ar', f'{fmt.ar or 44100}',
                 '-ac', f'{fmt.ac or 2}', '-f', ext, output)

    elif ext == 'webm':
        filters.append(scale(*fmt.bbox))
        if fmt.fps:
            filters.append(f'fps={fmt.fps}')
        with _complex_filter(extracts, filters) as script:
            _run('ffmpeg', '-y', '-i', asset.path, '-filter_complex_script', script,
                 '-row-mt', '1', '-b:v', '0', '-crf', f'{fmt.crf or 30}',
                 '-ar', f'{fmt.ar or 44100}', '-ac', f'{fmt.ac or 2}', '-f', ext, output)
'''
n = int(asset.duration / 30)
for i in range(n):
run('-ss', f'{(i + 0.5) * asset.duration / n}',
'-filter:v', "select='eq(pict_type, PICT_TYPE_I)'",
'-frames:v', '1', '-vsync', 'vfr', '-f', 'png', output)
'''
