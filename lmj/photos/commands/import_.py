import datetime
import lmj.cli
import lmj.photos
import os
import subprocess
import sys

cmd = lmj.cli.add_command('import')
cmd.add_argument('source', nargs='+', metavar='PATH',
                 help='import photos from these PATHs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = lmj.cli.get_logger(__name__)


def import_one(path):
    exif, = lmj.photos.parse(subprocess.check_output(['exiftool', '-json', path]))

    stamp = datetime.datetime.now()
    for key in 'DateTimeOriginal CreateDate ModifyDate FileModifyDate'.split():
        stamp = exif.get(key)
        if stamp:
            stamp = datetime.datetime.strptime(stamp[:19], '%Y:%m:%d %H:%M:%S')
            break

    photo = lmj.photos.insert(path)
    photo.exif = exif
    photo.meta = dict(stamp=stamp, user_tags=[], thumb=photo.thumb_path)
    photo.make_thumbnails(sizes=[('img', 700)])

    lmj.photos.update(photo)


def main(args):
    for src in args.source:
        for base, dirs, files in os.walk(src):
            dots = [n for n in dirs if n.startswith('.')]
            [dirs.remove(d) for d in dots]
            for name in files:
                if name.startswith('.'):
                    continue
                _, ext = os.path.splitext(name)
                if ext.lower()[1:] in 'gif jpg jpeg png tif tiff':
                    path = os.path.join(base, name)
                    if lmj.photos.exists(path):
                        logging.info('= %s', path)
                    else:
                        import_one(path)
                        logging.info('+ %s', path)
