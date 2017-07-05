import click
import collections
import contextlib
import glob
import multiprocessing as mp
import os
import re
import sys
import tempfile
import ujson
import zipfile

from .db import DB
from .media import Tag


def _process(jobs_queue, results_queue, callback):
    while True:
        job = jobs_queue.get()
        if job is None:
            break
        results_queue.put((job, callback(job)))


@contextlib.contextmanager
def workqueue(jobs, callback, num_workers=mp.cpu_count()):
    jobs_queue, results_queue = mp.Queue(), mp.Queue()
    args = (jobs_queue, results_queue, callback)
    workers = [mp.Process(target=_process, args=args) for _ in range(num_workers)]
    [w.start() for w in workers]
    for job in jobs:
        jobs_queue.put(job)
    [jobs_queue.put(None) for w in workers]
    try:
        yield results_queue
    except:
        # empty the jobs queue to force workers to halt.
        while not jobs_queue.empty():
            jobs_queue.get(False)
        raise
    [w.join() for w in workers]


class Importer(object):
    '''A class for importing media into the database.

    Parameters
    ----------
    db : str
        Filesystem path for our database.
    tags : list of str
        Extra tags to add to all imported items.
    path_tags : int
        Number of parent directory names to add as tags for each imported item.
    audio_formats : list of Format
      A list of Format tuples giving the formats for audio thumbnails.
    photo_formats : list of Format
      A list of Format tuples for photo thumbnails.
    video_formats : list of Format
      A list of Format tuples for video thumbnails.
    '''

    def __init__(self, db, tags, path_tags, audio_formats=(), video_formats=(),
                 photo_formats=()):
        self.db = DB(db)
        self.tags = tags
        self.path_tags = path_tags
        self.audio_formats = audio_formats
        self.photo_formats = photo_formats
        self.video_formats = video_formats

    def walk(self, roots):
        '''Recursively visit all files under the given root directories.

        Parameters
        ----------
        roots : sequence of str
            Root paths to search for files.

        Yields
        ------
        Filenames under each of the given root paths.
        '''
        for src in roots:
            for match in glob.glob(src):
                match = os.path.abspath(match)
                if os.path.isdir(match):
                    for base, dirs, files in os.walk(match):
                        dots = [n for n in dirs if n.startswith('.')]
                        [dirs.remove(d) for d in dots]
                        for name in files:
                            if not name.startswith('.'):
                                yield os.path.abspath(os.path.join(base, name))
                else:
                    yield match

    def run(self, roots):
        '''Run the import process in parallel on the given root paths.

        Parameters
        ----------
        roots : sequence of str
            Root paths to search for files.
        '''
        with workqueue(self.walk(roots), self):
            pass

    def __call__(self, path):
        '''Import a single path into the media database.

        Parameters
        ----------
        path : str
            A filesystem path to examine and possibly import.
        '''
        try:
            if self.db.exists(path):
                click.echo('{} Already have {}'.format(
                    click.style('=', fg='blue'),
                    click.style(path, fg='red')))
                return
            item = self.db.create(path)
            if item is None:
                click.echo('{} Unknown {}'.format(
                    click.style('?', fg='yellow'),
                    click.style(path, fg='red')))
                return
            for tag in self.tags:
                item.add_tag(tag)
            components = os.path.dirname(path).split(os.sep)[::-1]
            for i in range(self.path_tags):
                item.add_tag(components[i])
            item.save()
            cls = item.__class__.__name__.lower()
            for fmt in getattr(self, '{}_formats'.format(cls)):
                item.export(fmt=fmt)
            click.echo('{} Added {}'.format(
                    click.style('+', fg='green'),
                    click.style(path, fg='red')))
        except KeyboardInterrupt:
            self.db.delete(path)
        except:
            self.db.delete(path)
            _, exc, tb = sys.exc_info()
            click.echo('! Error {} {}'.format(path, exc))  # , ''.join(tb))


class Exporter(object):
    '''Export media content to a zip file on disk.

    Parameters
    ----------
    all_tags : list of :class:`Tag`
        All tags defined in the database.
    items : list of :class:`Media`
        A list of the media items to export.
    audio_formats : list of Format
      A list of Format tuples giving the formats for audio thumbnails.
    photo_formats : list of Format
      A list of Format tuples for photo thumbnails.
    video_formats : list of Format
      A list of Format tuples for video thumbnails.
    '''

    def __init__(self, all_tags, items, audio_formats=(), video_formats=(),
                 photo_formats=()):
        self.all_tags = all_tags
        self.items = items
        self.audio_formats = audio_formats
        self.photo_formats = photo_formats
        self.video_formats = video_formats

    def run(self, output, hide_tags=(), hide_metadata_tags=False,
            hide_datetime_tags=False, hide_omnipresent_tags=False):
        '''Export media to a zip archive.

        The zip archive will contain:

        - A file called index.json, containing a manifest of exported content.
        - A directory for each size, containing exported media data files.

        Parameters
        ----------
        output : str or file
            The name of a zip file to save, or a file-like object to write zip
            content to.
        hide_tags : list of str, optional
            A list of regular expressions matching tags to be excluded from the
            export information. For example, '^a' will exclude all tags
            starting with the letter "a". Default is to export all tags.
        hide_metadata_tags : bool, optional
            If True, export tags derived from EXIF data (e.g., ISO:1000, f/2,
            etc.) The default is not to export this information.
        hide_datetime_tags : bool, optional
            If True, export tags derived from time information (e.g., November,
            10am, etc.). The default is not to export this information.
        hide_omnipresent_tags : bool, optional
            If True, export tags present in all media. By default, tags that
            are present in all items being exported will not be exported.
        '''
        hide_sources = set()
        if hide_metadata_tags:
            hide_sources.add(Tag.METADATA)
        if hide_datetime_tags:
            hide_sources.add(Tag.DATETIME)

        hide_names = set()
        for pattern in hide_tags:
            for tag in self.all_tags:
                if re.match(pattern, tag.name):
                    hide_names.add(tag.name)
        if hide_omnipresent_tags:
            # count tag usage for this set of media.
            tag_counts = collections.defaultdict(int)
            for item in self.items:
                for tag in item.tags:
                    tag_counts[tag.name] += 1
            # remove tags that are applied to all media pieces.
            for name, count in tag_counts.items():
                if count == len(self.items):
                    hide_names.add(name)

        with tempfile.TemporaryDirectory() as root:
            index = os.path.join(root, 'index.json')
            self.root = root
            # export thumbnails in parallel, create index at the same time.
            with workqueue(self.items, self), open(index, 'w') as handle:
                export = []
                for item in self.items:
                    for tag in list(item.tags):
                        if tag.name in hide_names or tag.source in hide_sources:
                            item.remove_tag(tag)
                    export.append(item.rec)
                ujson.dump(export, handle)
            _create_zip(output, root)

        click.echo('Exported {} items to {}'.format(
            click.style(str(len(self.items)), fg='cyan'),
            click.style(output, fg='red')))

    def __call__(self, item):
        cls = item.__class__.__name__.lower()
        for fmt in getattr(self, '{}_formats'.format(cls)):
            item.export(fmt=fmt, root=self.root)


# This is mostly from zipfile.py in the Python source.
def _create_zip(output, root):
    def add(zf, path, zippath):
        if os.path.isfile(path):
            zf.write(path, zippath, zipfile.ZIP_DEFLATED)
        elif os.path.isdir(path):
            for x in os.listdir(path):
                add(zf, os.path.join(path, x), os.path.join(zippath, x))
    with zipfile.ZipFile(output, 'w') as zf:
        add(zf, root, os.path.splitext(os.path.basename(output))[0])
