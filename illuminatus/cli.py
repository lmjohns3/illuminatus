import click
import os

from .db import DB
from .media import Tag
from .importexport import Importer, Exporter

_DEFAULT_SIZES = (200, 1000)


@click.group()
@click.option('--db', envvar='ILLUMINATUS_DB', metavar='PATH',
              help='Load illuminatus database from PATH.')
@click.pass_context
def cli(ctx, db):
    '''Command-line interface for media management.'''
    if not db:
        raise click.UsageError('no --database specified!')
    ctx.obj = dict(db=db)


@cli.command()
@click.option('--order', default='stamp-', metavar='[stamp|path]',
              help='Sort records by this field. A "-" at the end reverses the order.')
@click.argument('query', nargs=-1)
@click.pass_context
def ls(ctx, query, order):
    '''List media matching a QUERY.

    Illuminatus queries permit a wide range of media selection, expressed using
    a set notation. The query syntax understands the following sets of media:

    \b
    - TAG -- media that are tagged with TAG
    - before:YYYY-MM-DD -- media with timestamps on or before YYYY-MM-DD
    - after:YYYY-MM-DD -- media with timestamps on or after YYYY-MM-DD
    - path:STRING -- media whose source path contains the given STRING

    Each pair of terms in a query is combined using one of the three set
    operators:

    \b
    - X & Y -- media in set X and in set Y
    - X | Y -- media in set X or set Y
    - X ~ Y -- media in set X but not in set Y

    Finally, parentheses can be used in the usual way, to group operations.
    '''
    def color(tag):
        if tag.source == Tag.METADATA:
            return 'cyan'
        if tag.source == Tag.DATETIME:
            return 'green'
        return 'yellow'

    for item in DB(ctx.obj['db']).select(' '.join(query), order=order):
        click.echo('{} {} {} {}'.format(
            click.style('{:05d}'.format(item.media_id), fg='red'),
            click.style(str(item.stamp)),
            ' '.join(click.style(t.name, fg=color(t)) for t in sorted(item.tags)),
            click.style(item.path)))


@cli.command()
@click.option('--hide-original', is_flag=True,
              help='"Delete" the source media file, by renaming it.')
@click.argument('query', nargs=-1)
@click.pass_context
def rm(ctx, query, hide_original):
    '''Remove media from the database.

    Media that are deleted from the database can additionally be "removed" from
    the filesystem by specifying an extra flag. The "removal" takes place by
    renaming the original source file with an ".illuminatus-removed-" prefix.
    An offline process (e.g., a cron script) can garbage-collect these renamed
    files as needed.
    '''
    for item in DB(ctx.obj['db']).select(' '.join(query)):
        item.delete(hide_original=hide_original)


@cli.command()
@click.option('--output', metavar='FILE', help='save export zip to FILE')
@click.option('--size', metavar='N', type=int, multiple=True,
              help='Save thumbnails to fit inside an NxN box.')
@click.option('--hide-tags', multiple=True, metavar='REGEXP',
              help='Exclude tags matching REGEXP from exported items.')
@click.option('--hide-datetime-tags', default=False, is_flag=True,
              help='Include tags related to timestamp data.')
@click.option('--hide-metadata-tags', default=False, is_flag=True,
              help='Include tags from media metadata like EXIF.')
@click.option('--hide-omnipresent-tags', default=False, is_flag=True,
              help='Do not remove tags that are present in all items.')
@click.argument('query', nargs=-1)
@click.pass_context
def export(ctx, query, size, **kwargs):
    '''Export media as a zip file.

    Media can be selected using an illuminatus QUERY, and then multiple sizes
    of thumbnails are generated and saved along with a JSON index.
    '''
    db = DB(ctx.obj['db'])
    size = size or _DEFAULT_SIZES
    Exporter(db.tags, db.select(' '.join(query))).run(size=size, **kwargs)


@cli.command('import')
@click.option('--tag', multiple=True, metavar='TAG',
              help='Add TAG to all imported items.')
@click.option('--path-tags', default=0, metavar='N',
              help='Add N parent directories as tags.')
@click.option('--size', metavar='N', type=int, multiple=True,
              help='Save thumbnails to fit inside an NxN box.')
@click.argument('source', nargs=-1)
@click.pass_context
def import_(ctx, tag, path_tags, size, source):
    '''Import media into the illuminatus database.

    If any SOURCE is a directory, all media under that directory will be
    imported recursively.
    '''
    size = size or _DEFAULT_SIZES
    Importer(ctx.obj['db'], tag, path_tags, size).run(source)


@cli.command()
@click.option('--stamp', type=str,
              help='Modify the timestamp of matching records.')
@click.option('--add-tag', type=str, multiple=True, metavar='TAG')
@click.option('--remove-tag', type=str, multiple=True, metavar='TAG')
@click.option('--add-path-tags', default=0, metavar='N',
              help='Add N parent directories as tags.')
@click.argument('query', nargs=-1)
@click.pass_context
def modify(ctx, query, add_tag, remove_tag, add_path_tags, stamp):
    '''Modify media items in the database.

    Common tasks are adding or removing tags, or updating the timestamps
    associated with one or more media items (e.g., to adjust for a
    miscalibrated camera or the like).

    The --stamp option can take two different types of timestamp specifiers.
    If this option is passed a timestamp string, it will replace the current
    timestamp for all matching media. Otherwise it can contain any number
    of strings of the form 'sNx' which will adjust timestamp unit x by
    N units either later (if s is '+') or earlier (if s is '-'). For
    example, '+3y,-2h' will shift the timestamp of all matching media
    three years later and two hours earlier. Here x can be 'y' (year),
    'm' (month), 'd' (day), or 'h' (hour).
    '''
    for item in DB(ctx.obj['db']).select(' '.join(query)):
        for tag in add_tag:
            item.add_tag(tag)
        for tag in remove_tag:
            item.remove_tag(tag)
        if add_path_tags > 0:
            components = os.path.dirname(item.path).split(os.sep)[::-1]
            for i in range(add_path_tags):
                tags.append(components[i])
        if stamp:
            item.update_stamp(stamp)
        item.save()


@cli.command()
@click.option('--root', metavar='PATH', help='Save thumbnails under PATH.')
@click.option('--size', metavar='N', type=int, multiple=True,
              help='Save thumbnails to fit inside an NxN box.')
@click.argument('query', nargs=-1)
@click.pass_context
def thumbnail(ctx, query, size, root):
    '''Generate thumbnails for media items.

    Media are selected using an illuminatus QUERY, and thumbnails can be
    generated in one or more sizes.
    '''
    for item in DB(ctx.obj['db']).select(' '.join(query)):
        for s in size or _DEFAULT_SIZES:
            item.thumbnail(s, root)


@cli.command()
@click.option('--host', default='localhost', metavar='HOST',
              help='Run server on HOST.')
@click.option('--port', default=5555, metavar='PORT',
              help='Run server on PORT.')
@click.option('--debug/--no-debug', default=False)
@click.option('--hide-originals/--no-hide-originals', default=False)
@click.pass_context
def serve(ctx, host, port, debug, hide_originals):
    '''Start an HTTP server for media metadata.'''
    from .serve import app
    app.config['db'] = db = DB(ctx.obj['db'])
    app.config['hide-originals'] = hide_originals
    app.config['sizes'] = sorted(
        (d for d in os.listdir(db.root) if d.isdigit()),
        key=lambda d: int(d))
    app.run(host=host, port=port, debug=debug, threaded=True)
