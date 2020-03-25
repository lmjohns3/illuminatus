import click
import itertools
import json
import math
import os
import subprocess
import tempfile

_DEBUG = 0


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


def _scale(w, h):
    return f'scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos'


def _rotate(r):
    return f'rotate={r}:ow=rotw({r}):oh=roth({r})'


def _sigmoid(ratio):
    def curve(x):
        return (x ** ratio if x < 0.5 else
                1 - curve(1 - x) if x > 0.5 else
                0.5)
    return ' '.join(f'{x}/{curve(x)}' for x in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0))


def _apply_filters(asset):
    '''Apply a filter using this tool.

    Parameters
    ----------
    asset : :class:`Asset`
        Asset to use for media data.

    Returns
    -------
    slices : list of (float, float)
        List of slices from the source asset.
    filters : list of str
        List of filters to apply.
    '''
    # A list of extracted parts from the original video; these will be extracted
    # and concatenated (in the order in this list) before applying filters.
    slices = []
    filters = []

    runners = dict(
        autocontrast=lambda percent: filters.append(f'histeq=strength={percent / 100}'),
        brightness=lambda percent: filters.append(f'hue=b={percent / 100 - 1}'),
        contrast=lambda percent: filters.append(f"curves=m='{_sigmoid(percent / 100)}'"),
        crop=lambda w, h, x, y: filters.append(f'crop={w}:{h}:{x}:{y}'),
        extract=lambda start, duration: slices.append((start, duration)),
        fps=lambda fps: filters.append(f'fps={fps}'),
        hflip=lambda: filters.append('hflip'),
        hue=lambda degrees: filters.append(f'hue=h={degrees}'),
        rotate=lambda degrees: filters.append(_rotate(math.radians(degrees))),
        saturation=lambda percent: filters.append(f'hue=s={percent / 100}'),
        scale=lambda w, h: filters.append(_scale(w, h)),
        vflip=lambda: filters.append('vflip'),
    )

    w, h, t = asset.width, asset.height, asset.duration
    for kwargs in json.loads(asset.filters):
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

    return slices, filters


def _generate_chains(use_video, use_audio, slices, filters):
    # https://superuser.com/questions/681885
    pads = []
    for i, (start, duration) in enumerate(slices):
        if use_video:
            pads.append(f'{i+1}v')
            yield ['0:v'], [f'trim={start}:{start + duration}',
                            'setpts=PTS-STARTPTS',
                            'format=yuv420p'], [pads[-1]]
        if use_audio:
            pads.append(f'{i+1}a')
            yield ['0:a'], [f'atrim={start}:{start + duration}',
                            'asetpts=PTS-STARTPTS'], [pads[-1]]
    if pads:
        outs = (([f'outv'] if use_video else []) +
                ([f'outa'] if use_audio else []))
        use_v = int(use_video)
        use_a = int(use_audio)
        n = len(pads) // (use_v + use_a)
        yield pads, [f'concat=n={n}:v={use_v}:a={use_a}'], outs
    if filters:
        yield [], filters, ['outv']


_encoder_args = dict(
    # https://superuser.com/questions/1296374
    mp4=('-c:v h264_nvenc -level:v 4.1 -profile:v main -rc:v vbr_hq '
         '-rc-lookahead:v 32 -c:a aac'),
    webm='-c:v libvpx-vp9 -c:a libopus -row-mt 1',
)


def run(asset, fmt, output):
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
    slices, filters = _apply_filters(asset)
    if hasattr(fmt, 'bbox'):
        filters.append(_scale(*fmt.bbox))
    if hasattr(fmt, 'fps'):
        filters.append(f'fps={fmt.fps}')

    format_args = []
    for attr in 'ar ac crf quality speed'.split():
        if hasattr(fmt, attr):
            format_args.extend((f'-{attr}', f'{getattr(fmt, attr)}'))
    format_args = tuple(format_args)

    stem = os.path.splitext(output)[0]

    def run(*args):
        cmd = ('ffmpeg', '-y', '-i', asset.path) + format_args + args
        if _DEBUG > 0:
            click.echo('{}: {}'.format(
                click.style('FFMPEG', bold=True),
                click.style(' '.join(cmd), bold=True, fg='blue')))
        return subprocess.run(cmd, capture_output=_DEBUG == 0)

    # Audio --> png: make a spectrogram image of the middle 60 seconds.
    if asset.is_audio and fmt.ext == 'png':
        t = asset.duration / 2
        trim = f'atrim={max(0, t - 30)}:{min(asset.duration, t + 30)}'
        w, h = fmt.bbox
        spec = f'showspectrumpic=s={w}x{h}:color=viridis:scale=log:fscale=log'
        return run('-af', f'{trim},{spec}', f'{stem}.png')

    # Video --> gif: make an animated gif from the middle 10 seconds of a video,
    # and a poster image from the start of that clip.
    if asset.is_video and fmt.ext == 'gif':
        args = ('-ss', f'{max(0, asset.duration / 2 - 5)}', '-t', '10', '-an', '-vf')
        scale = _scale(*fmt.bbox)
        palette = 'split[u][q];[u]fifo[v];[q]palettegen[p];[v][p]paletteuse'
        run(*args + (f'fps={fmt.fps},{scale},{palette}', '-loop', '-1', f'{stem}.gif'))
        return run(*args + (scale, '-frames:v', '1', f'{stem}.png'))

    # Video --> webp: make an animation from the middle 10 seconds of a video,
    # and a poster image from the start of that clip.
    if asset.is_video and fmt.ext == 'webp':
        args = ('-ss', f'{max(0, asset.duration / 2 - 5)}', '-t', '10', '-an', '-vf')
        scale = _scale(*fmt.bbox)
        run(*args + (f'fps={fmt.fps},{scale}', '-codec:v', 'libwebp', f'{stem}.webp'))
        return run(*args + (scale, '-frames:v', '1', f'{stem}.png'))

    # Default output, no more funny business.
    with tempfile.NamedTemporaryFile(mode='w+') as script:
        pads = []
        video_pad, audio_pad = '0:v?', '0:a?'
        for inputs, chain, outputs in _generate_chains(
                use_video=asset.is_video or asset.is_photo,
                use_audio=asset.is_video or asset.is_audio,
                slices=slices, filters=filters):
            if pads:
                script.write(';\n')
            script.write(''.join(f'[{i}]' for i in inputs))
            script.write(','.join(chain))
            script.write(''.join(f'[{o}]' for o in outputs))
            pads = outputs
            for p in pads:
                if p.endswith('v'):
                    video_pad = f'[{p}]'
                if p.endswith('a'):
                    audio_pad = f'[{p}]'
        script.flush()
        if _DEBUG:
            print('-------->8-------')
            subprocess.run(['cat', script.name])
            print()
            print('-------8<--------')
        args = []
        if pads:
            args.extend(('-filter_complex_script', script.name,
                         '-map', video_pad, '-map', audio_pad))
        if hasattr(fmt, 'abr'):
            args.extend(('-b:a', f'{fmt.abr}k'))
        if hasattr(fmt, 'vbr'):
            args.extend(('-b:v', f'{fmt.vbr}k'))
        run(*args + _encoder_args.get(fmt.ext, '').split() + [
            '-avoid_negative_ts', '1', '-g', '240', output])
'''
n = int(asset.duration / 30)
for i in range(n):
run('-ss', f'{(i + 0.5) * asset.duration / n}',
'-filter:v', "select='eq(pict_type, PICT_TYPE_I)'",
'-frames:v', '1', '-vsync', 'vfr', '-f', 'png', output)
'''
