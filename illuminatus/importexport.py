import click
import collections
import glob
import mimetypes
import multiprocessing as mp
import os
import re
import sys
import tempfile
import zipfile

from . import db
from . import metadata

_DEBUG = 0


def _to_format(kwargs):
    return collections.namedtuple('Format', sorted(kwargs))(**kwargs)


def _process(jobs_queue, callback):
    while True:
        job = jobs_queue.get()
        if job is None:
            break
        callback(job)


def run_workqueue(jobs, callback, num_workers=None):
    if _DEBUG:
        return [callback(j) for j in jobs]
    jobs_queue = mp.Queue()
    if not num_workers:
        num_workers = mp.cpu_count()
    workers = [mp.Process(target=_process, args=(jobs_queue, callback))
               for _ in range(num_workers)]
    [w.start() for w in workers]
    for job in jobs:
        jobs_queue.put(job)
    [jobs_queue.put(None) for w in workers]
    try:
        [w.join() for w in workers]
    except:
        # empty the jobs queue to force workers to halt.
        while not jobs_queue.empty():
            jobs_queue.get(False)
        raise
    finally:
        [w.terminate() for w in workers]


def walk(roots):
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


def _guess_medium(path):
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
    for pattern, medium in (('audio/.*', db.Asset.Medium.Audio),
                            ('video/.*', db.Asset.Medium.Video),
                            ('image/.*', db.Asset.Medium.Photo)):
        if re.match(pattern, mime):
            return medium
    return None


class Importer:
    '''A class for importing media into the database.

    Parameters
    ----------
    db : str
        Filesystem path for our database.
    tags : list of str
        Extra tags to add to all imported assets.
    path_tags : int
        Number of parent directory names to add as tags for each imported asset.
    '''

    def __init__(self, session, tags, path_tags):
        self.session = session
        with session() as sess:
            self.tags = set(db.Tag.get_or_create(sess, t) for t in tags)
        self.path_tags = path_tags

    def run(self, roots):
        '''Run the import process in parallel on the given root paths.

        Parameters
        ----------
        roots : sequence of str
            Root paths to search for files.
        '''
        run_workqueue(walk(roots), self.import_one)

    def import_one(self, path):
        '''Import a single path into the media database.

        Parameters
        ----------
        path : str
            A filesystem path to examine and possibly import.
        '''
        try:
            with self.session() as sess:
                if sess.query(db.Asset).filter(db.Asset.path == path).count():
                    click.echo('{} Already have {}'.format(
                        click.style('=', fg='blue'),
                        click.style(path, fg='red')))
                    return
                medium = _guess_medium(path)
                if medium is None:
                    click.echo('{} Unknown {}'.format(
                        click.style('?', fg='yellow'),
                        click.style(path, fg='red')))
                    return
                asset = db.Asset(path=path, medium=medium)
                asset.tags |= self.tags
                components = os.path.dirname(path).split(os.sep)[::-1]
                for i in range(self.path_tags):
                    asset.tags.add(db.Tag.get_or_create(sess, components[i]))
                sess.add(asset)
                click.echo('{} Added {}'.format(
                        click.style('+', fg='green'),
                        click.style(path, fg='red')))
        except KeyboardInterrupt:
            return
        except:
            _, exc, tb = sys.exc_info()
            click.echo('! Error {} {}\n{}'.format(path, exc, ''.join(tb)))


class Thumbnailer:
    '''Export thumbnails of media content to files on disk.

    Parameters
    ----------
    assets : list of :class:`db.Asset`
        A list of the media assets to thumbnail.
    root : str
        A filesystem path for saving thumbnails.
    overwrite : bool
        If True, we'll overwrite existing thumbnails.
    formats : list of dict
        The formats we should use for making thumbnails.
    '''

    def __init__(self, assets, root=None, overwrite=False, formats=None):
        self.assets = assets
        self.root = root
        self.overwrite = overwrite
        self.formats = formats

    def run(self):
        '''Export thumbnails for media to files on disk.'''
        for medium in db.Asset.Medium:
            assets = [a for a in self.assets if a.medium == medium]
            if assets:
                run_workqueue(assets, self, int(medium == db.Asset.Medium.Video))

    def __call__(self, asset):
        for fmt in self.formats:
            if fmt.get('medium', '') != asset.medium.name.lower():
                continue
            root = self.root
            if 'path' in fmt:
                root = os.path.join(root, fmt['path'])
            output = asset.export(
                fmt=_to_format(fmt['format']), root=root, overwrite=self.overwrite)
            if not output:
                continue
            click.echo('{} {} -> {}'.format(click.style('*', fg='cyan'),
                                            click.style(asset.path, fg='red'),
                                            output))


class Exporter:
    '''Export media content to a zip file on disk.

    Parameters
    ----------
    all_tags : list of :class:`db.Tag`
        All tags defined in the database.
    assets : list of :class:`db.Asset`
        A list of the assets to export.
    formats : list of dict
        The formats that we should use for the export.
    '''

    def __init__(self, all_tags, assets, formats):
        self.all_tags = all_tags
        self.assets = assets
        self.formats = formats

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
            export information. For example, 'a.*' will exclude all tags
            starting with the letter "a". Default is to export all tags.
        hide_metadata_tags : bool, optional
            If True, export tags derived from EXIF data (e.g., ISO:1000, f/2,
            etc.) The default is not to export this information.
        hide_datetime_tags : bool, optional
            If True, export tags derived from time information (e.g., November,
            10am, etc.). The default is not to export this information.
        hide_omnipresent_tags : bool, optional
            If True, export tags present in all media. By default, tags that
            are present in all assets being exported will not be exported.
        '''
        hide_patterns = list(hide_tags)
        if hide_metadata_tags:
            hide_patterns.append(db.Tag.METADATA_PATTERN)
        if hide_datetime_tags:
            hide_patterns.append(db.Tag.DATETIME_PATTERN)

        hide_names = set()
        for pattern in hide_patterns:
            for tag in self.all_tags:
                if re.match(pattern, tag.name):
                    hide_names.add(tag.name)
        if hide_omnipresent_tags:
            # count tag usage for this set of assets.
            tag_counts = collections.defaultdict(int)
            for asset in self.assets:
                for tag in asset.tags:
                    tag_counts[tag.name] += 1
            # remove tags that are applied to all assets.
            for name, count in tag_counts.items():
                if count == len(self.assets):
                    hide_names.add(name)

        with tempfile.TemporaryDirectory() as root:
            index = os.path.join(root, 'index.json')
            self.root = root
            run_workqueue(self.assets, self)
            with open(index, 'w') as handle:
                json.dump([asset.to_dict(exclude_tags=hide_names)
                           for asset in self.assets], handle)
            _create_zip(output, root)

        return len(self.assets)

    def __call__(self, asset):
        for fmt in self.formats:
            if fmt.medium != asset.medium.name.lower():
                continue
            root = self.root
            if 'path' in fmt:
                root = os.path.join(root, fmt['path'])
            asset.export(fmt=_to_format(fmt['format']), root=root)


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
