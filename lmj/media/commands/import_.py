import climate
import fnmatch
import lmj.media
import mimetypes
import os
import sys
import traceback

cmd = climate.add_command('import')
cmd.add_argument('--tag', default=[], nargs='+', metavar='TAG',
                 help='apply these TAGs to all imported photos')
cmd.add_argument('--add-path-tag', action='store_true',
                 help='use the parent DIR as a tag for each import')
cmd.add_argument('source', nargs='+', metavar='PATH',
                 help='import photos from these PATHs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger('lmj.media.import')


def find_class_for(mime):
    '''Find a media class for the given mime type.'''
    if mime:
        for cls in (lmj.media.Photo, ):
            for pattern in cls.MIME_TYPES:
                if fnmatch.fnmatch(mime, pattern):
                    return cls
    return None


def maybe_import(args, path):
    '''Given a path, try to import it.'''
    mime, _ = mimetypes.guess_type(path)
    cls = find_class_for(mime)
    if cls is None:
        logging.info('? %s %s', mime, path)
        return None
    if lmj.media.db.exists(path):
        logging.info('= %s %s', mime, path)
        return None
    try:
        cls.create(path, args.tag, args.add_path_tag)
        logging.warn('+ %s %s', mime, path)
    except KeyboardInterrupt:
        lmj.media.db.remove_path(path)
        return None
    except:
        lmj.media.db.remove_path(path)
        _, exc, tb = sys.exc_info()
        return path, exc, traceback.format_tb(tb)


def main(args):
    errors = []
    for src in args.source:
        for base, dirs, files in os.walk(src):
            dots = [n for n in dirs if n.startswith('.')]
            [dirs.remove(d) for d in dots]
            for name in files:
                if name.startswith('.'):
                    continue
                err = maybe_import(args, os.path.join(base, name))
                if err:
                    errors.append(err)
    for path, exc, tb in errors:
        logging.error('! %s %s', path, exc)#, ''.join(tb))
