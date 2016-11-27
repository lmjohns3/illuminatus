import climate
import illuminatus
import multiprocessing as mp
import os
import sys
import traceback

cmd = climate.add_command('import')
cmd.add_argument('--tag', default=[], nargs='+', metavar='TAG',
                 help='apply these TAGs to all imported photos')
cmd.add_argument('--path-tags', default=0, type=int, metavar='N',
                 help='use N parent DIRs as tags for each imported item')
cmd.add_argument('source', nargs='+', metavar='PATH',
                 help='import photos from these PATHs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger(__name__)


def maybe_import(db, args, path):
    '''Given a path, try to import it.'''
    if db.exists(path):
        logging.info('= %s', path)
        return None
    try:
        db.create(path, tags=args.tag, path_tags=args.path_tags)
        logging.warn('+ %s', path)
    except ValueError:
        logging.info('? %s', path)
        return None
    except KeyboardInterrupt:
        db.delete(path)
        return None
    except:
        db.delete(path)
        _, exc, tb = sys.exc_info()
        return exc, traceback.format_tb(tb)


def process(db, args, queue):
    '''Process paths from a workqueue until there is no more work.'''
    err = None
    while True:
        path = queue.get()
        if path is None:
            break
        err = maybe_import(db, args, path)
        if err:
            exc, tb = err
            logging.error('! %s %s', path, exc)  # , ''.join(tb))


def main(db, args):
    errors = []
    queue = mp.Queue()
    workers = [mp.Process(target=process, args=(db, args, queue))
               for _ in range(mp.cpu_count())]
    [w.start() for w in workers]

    def cleanup():
        [queue.put(None) for _ in workers]
        [w.join() for w in workers]

    try:
        for src in args.source:
            for base, dirs, files in os.walk(src):
                dots = [n for n in dirs if n.startswith('.')]
                [dirs.remove(d) for d in dots]
                for name in files:
                    if not name.startswith('.'):
                        queue.put(os.path.join(base, name))
        cleanup()
    except KeyboardInterrupt:
        # empty the queue to force workers to halt.
        while not queue.empty():
            queue.get(False)
    cleanup()
