import base64
import click
import collections
import glob
import hashlib
import json
import logging
import mimetypes
import os
import re
import tempfile
import zipfile

from . import db
from . import tasks
from .assets import Asset
from .tags import Tag


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


def maybe_import_asset(sess, path, tags=(), path_tags=0):
    '''Import a single asset into the database.

    Parameters
    ----------
    sess : db.Session
        Database session for the import.
    path : str
        A filesystem path to examine and possibly import.
    tags : set of str
        Tags to add to this asset.
    path_tags : int
        Number of path (directory) name components to add as tags.
    '''
    bold = click.style(path, bold=True)

    def color(s, fg):
        return click.style(s, fg=fg)

    digest = hashlib.blake2s(path.encode('utf-8')).digest()
    slug = base64.b64encode(digest, b'-_').strip(b'=').decode('utf-8')

    medium = None
    mime, _ = mimetypes.guess_type(path)
    for pattern, med in (('audio/.*', 'audio'),
                         ('video/.*', 'video'),
                         ('image/.*', 'photo')):
        if mime and re.match(pattern, mime):
            medium = med
            break
    if medium is None:
        click.echo(f'{color("?", "yellow")} {slug} {bold}')
        return

    if sess.query(Asset).filter(Asset.slug == slug).count():
        click.echo(f'{color("=", "blue")} {slug} {bold}')
        sess.close()
        return

    asset = Asset(path=path, medium=medium, slug=slug)
    asset.tags.update(tags)
    asset.add_path_tags(path_tags)

    try:
        sess.add(asset)
        sess.commit()
        click.echo(f'{color("+", "cyan")} {slug} {bold}')
        return tasks.update_from_content.delay(slug)
    except:
        sess.rollback()
        logging.error(f'{color("!", "red")} {slug} {bold}')
        logging.exception('')
    finally:
        sess.close()


def export_for_web(assets, root, formats, overwrite):
    '''Export assets asynchronously to a root dir in preparation for zipping.

    Parameters
    ----------
    assets : list of :class:`db.Asset`
        A list of the assets to export.
    root : str
        A directory containing thumbnails to include in the zip.
    formats : str
        The name of a thumbnail format configuration file to load.
    overwrite : bool
        If True, overwrite existing thumbnails.

    Yields
    ------
    Asynchronous results from each asset export task.
    '''
    with open(formats) as handle:
        formats = json.load(handle)
    for asset in assets:
        for path, kwargs in formats[asset.medium].items():
            kw = dict(slug=asset.slug,
                      overwrite=overwrite,
                      dirname=os.path.join(root, path, asset.slug[:1]))
            kw.update(kwargs)
            queue = 'video' if asset.is_video and path == 'medium' else 'celery'
            yield tasks.export.apply_async(kwargs=kw, queue=queue)


def export_for_zip(assets, root, formats):
    '''Export assets asynchronously to a root dir in preparation for zipping.

    Parameters
    ----------
    assets : list of :class:`db.Asset`
        A list of the assets to export.
    root : str
        A directory containing thumbnails to include in the zip.
    formats : str
        The name of a thumbnail format configuration file to load.

    Yields
    ------
    Asynchronous results from each asset export task.
    '''
    with open(formats) as handle:
        formats = json.load(handle)
    for asset in assets:
        medium_ext = dict(audio='mp3', photo='jpg', video='mp4')[medium]
        stems = [asset.stamp.isoformat()[:10], asset.slug[:4]]
        for tag in sorted(asset._tags, key=lambda t: t.name):
            if tag.is_user:
                stems.append(tag.name)
        stem = '-'.join(stems)
        for path, kwargs in formats[asset.medium].items():
            kw = dict(slug=asset.slug,
                      dirname=os.path.join(root, path),
                      basename=f'{stem}.{kwargs.get("ext", medium_ext)}')
            kw.update(kwargs)
            queue = 'video' if asset.is_video and path == 'medium' else 'celery'
            yield tasks.export.apply_async(kwargs=kw, queue=queue)


def export_zip(assets, root, output, hide_tags=(), hide_omnipresent_tags=False):
    '''Create a zip archive.

    The zip archive will contain:

    - A file called index.json, containing a manifest of exported content.
    - A directory for each size, containing exported media data files.

    Parameters
    ----------
    assets : list of :class:`db.Asset`
        A list of the assets to export.
    root : str
        A directory containing thumbnails to include in the zip.
    output : str or file
        The name of a zip file to save, or a file-like object to write zip
        content to.
    hide_tags : list of str, optional
        A list of regular expressions matching tags to be excluded from the
        export information. For example, 'a.*' will exclude all tags
        starting with the letter "a". Default is to export all tags.
    hide_omnipresent_tags : bool, optional
        If True, export tags present in all media. By default, tags that
        are present in all assets being exported will not be exported.
    '''
    tag_counts = collections.defaultdict(int)
    for asset in assets:
        for tag in asset.tags:
            tag_counts[tag] += 1

    exclude_tags = {tag for tag, count in tag_counts.items()
                    if (hide_omnipresent_tags and count == len(assets) or
                        any(re.match(patt, tag) for patt in hide_tags))}

    items = [asset.to_dict() for asset in assets]
    for item in items:
        item['tags'] = list(set(item['tags']) - exclude_tags)
    with open(os.path.join(root, 'index.json'), 'w') as handle:
        json.dump(items, handle)

    # This is mostly from zipfile.py in the Python source.
    def add(zf, path, zippath):
        if os.path.isfile(path):
            zf.write(path, zippath, zipfile.ZIP_DEFLATED)
        elif os.path.isdir(path):
            for x in os.listdir(path):
                add(zf, os.path.join(path, x), os.path.join(zippath, x))

    with zipfile.ZipFile(output, 'w') as zf:
        add(zf, root, os.path.splitext(os.path.basename(output))[0])
