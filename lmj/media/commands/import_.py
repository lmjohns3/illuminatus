import datetime
import lmj.cli
import lmj.photos
import os
import sys
import traceback

cmd = lmj.cli.add_command('import')
cmd.add_argument('--tag', default=[], nargs='+', metavar='TAG',
                 help='apply these TAGs to all imported photos')
cmd.add_argument('--add-path-tag', action='store_true',
                 help='use the parent DIR as a tag for each import')
cmd.add_argument('source', nargs='+', metavar='PATH',
                 help='import photos from these PATHs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = lmj.cli.get_logger(__name__)


def compute_timestamp_from(exif, key):
    raw = exif.get(key)
    if not raw:
        return None
    for fmt in ('%Y:%m:%d %H:%M:%S', '%Y:%m:%d %H:%M+%S'):
        try:
            return datetime.datetime.strptime(raw[:19], fmt)
        except:
            pass
    return None


def import_one(path, tags, add_path_tag=False):
    p = lmj.photos.db.insert(path)

    stamp = None
    for key in ('DateTimeOriginal', 'CreateDate', 'ModifyDate', 'FileModifyDate'):
        stamp = compute_timestamp_from(p.exif, key)
        if stamp:
             break
    if stamp is None:
        stamp = datetime.datetime.now()

    tags = list(tags)
    if add_path_tag:
        tags.append(os.path.basename(os.path.dirname(path)))

    p.meta = dict(
        stamp=stamp,
        thumb=p.thumb_path,
        user_tags=sorted(lmj.photos.util.normalized_tag_set(tags)),
        exif_tags=sorted(lmj.photos.util.tags_from_exif(p.exif)))

    logging.info('user: %s; exif: %s',
                 ', '.join(p.meta['user_tags']),
                 ', '.join(p.meta['exif_tags']),
                 )

    p.make_thumbnails()

    lmj.photos.db.update(p)


def main(args):
    errors = []
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
                    if lmj.photos.db.exists(path):
                        logging.info('= %s', path)
                        continue
                    try:
                        import_one(path, args.tag, args.add_path_tag)
                        logging.warn('+ %s', path)
                    except KeyboardInterrupt:
                        lmj.photos.db.remove_path(path)
                        break
                    except:
                        _, exc, tb = sys.exc_info()
                        errors.append((path, exc, traceback.format_tb(tb)))
                        lmj.photos.db.remove_path(path)

    for path, exc, tb in errors:
        logging.error('! %s %s', path, exc)#, ''.join(tb))