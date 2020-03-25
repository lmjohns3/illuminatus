import click
import contextlib
import json
import logging
import os
import sys

from . import db
from . import importexport
from . import tasks

from .assets import Asset


@contextlib.contextmanager
def transaction():
    sess = Session()
    try:
        yield sess
        sess.commit()
    except:
        sess.rollback()
        raise
    finally:
        sess.close()


def display(asset, include_tags='.*', exclude_tags=None):
    tags = sorted((t for t in asset.tags if re.match(include_tags, t.name)),
                  key=lambda t: (t.pattern, t.name))
    return (
        asset.slug,
        ' '.join(sorted(str(h) for h in asset.hashes if len(h.nibbles) < 8)),
        ' '.join(t.name_string for t in tags),
        click.style(asset.path),
    )


@click.group()
@click.option('--db-path', envvar='ILLUMINATUS_DB', metavar='PATH',
              default='', help='Load database from PATH.')
@click.option('--log-sql/--no-log-sql', default=False,
              help='Log database queries.')
@click.option('--log-tools/--no-log-tools', default=False,
              help='Log tool commands.')
@click.pass_context
def cli(ctx, db_path, log_sql, log_tools):
    '''Command-line interface for media database.'''
    # Don't require a database for getting help.
    if ctx.invoked_subcommand == 'help' or '--help' in sys.argv:
        return

    if ctx.invoked_subcommand != 'init':
        if not os.path.isfile(db_path):
            raise RuntimeError('Illuminatus database not found: {}'.format(
                click.style(db_path, fg='cyan')))

    if not db_path:
        db_path = click.prompt('Illuminatus database file')
    db_path = os.path.abspath(os.path.expanduser(db_path))
    ctx.obj = dict(db_path=db_path)

    # Configure sqlalchemy sessions to connect to our database.
    db.Session.configure(bind=db.engine(path=db_path, echo=log_sql))

    if log_tools:
        from . import ffmpeg
        ffmpeg._DEBUG = 1


@cli.command()
@click.pass_context
def help(ctx):
    '''Help on QUERYs.

    \b
    Queries
    =======

    Queries permit a wide range of media selection, expressed using a set
    notation. The query syntax understands the following sets of media:

    \b
    - TAG -- assets that are tagged with TAG
    - before:YYYY-MM-DD -- assets with timestamps on or before YYYY-MM-DD
    - during:YYYY-MM -- assets with timestamps in the range YYYY-MM
    - after:YYYY-MM-DD -- assets with timestamps on or after YYYY-MM-DD
    - path:STRING -- assets whose source path contains the given STRING
    - hash:STRING -- assets whose hash contains the given STRING
    - audio/photo/video -- assets that are audio, photo, or video

    Each of the terms in a query is combined using one of the three set
    operators:

    \b
    - X Y -- media in set X and in set Y
    - X or Y -- media in set X or set Y
    - not Y -- media not in set Y

    Finally, parentheses can be used in the usual way, to group operations.

    \b
    Examples
    --------

    \b
    - cake
      selects everything tagged "cake"
    - cake not ice-cream
      selects everything tagged "cake" that is not also tagged "ice-cream"
    - cake ice-cream
      selects everything tagged with both "cake" and "ice-cream"
    - cake before:2010-03-14
      selects everything tagged "cake" from before pi day 2010
    - cake (before:2010-03-14 or after:2011-03-14)
      selects everything tagged "cake" that wasn't between pi day 2010 and
      pi day 2011
    '''
    print(ctx.get_help())


@cli.command()
@click.pass_context
def init(ctx):
    '''Initialize a new database.'''
    models.Model.metadata.create_all(db.engine(ctx.obj['db_path']))


@cli.command()
@click.option('--order', default='stamp-', metavar='[stamp|path]',
              help='Sort records by this field. A "-" at the end reverses the order.')
@click.option('--limit', default=0, metavar='N', help='Limit to N records.')
@click.argument('query', nargs=-1)
@click.pass_context
def ls(ctx, query, order, limit):
    '''List assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    with db.transaction() as sess:
        for asset in models.Asset.matching(sess, ' '.join(query), order, limit):
            click.echo(' '.join(display(asset)))


@cli.command()
@click.option('--hash', default='DIFF_4', metavar='[DIFF_8|RGB_HIST_32|...]',
              help='Check for asset neighbors using this hash.')
@click.option('--distance', default=1, metavar='N',
              help='Look within a Hamming distance of N for hash neighbors.')
@click.argument('query', nargs=-1)
@click.pass_context
def dupe(ctx, query, hash, distance):
    '''List duplicate assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    with db.transaction() as sess:
        for asset in models.Asset.matching(sess, ' '.join(query)):
            neighbors = asset.select_similar(sess, hash=hash, distance=distance)
            if neighbors:
                click.echo(' '.join(display(asset)))
                for neighbor in neighbors:
                    click.echo(' '.join(('-->', ) + display(neighbor)))
                click.echo('')


@cli.command()
@click.option('--hide-original/--no-hide-original', default=False,
              help='"Delete" the source file, by renaming it.')
@click.argument('query', nargs=-1)
@click.pass_context
def rm(ctx, query, hide_original):
    '''Remove assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.

    Assets that are deleted from the database can additionally be "removed"
    from the filesystem by specifying an extra flag. The "removal" takes place
    by renaming the original source file with an ".illuminatus-removed-"
    prefix. An offline process (e.g., a cron script) can garbage-collect these
    renamed files as needed.
    '''
    with db.transaction() as sess:
        for asset in queries.matching(sess.query(models.Asset), query):
            if hide_original:
                tasks.hide_original(asset.path)
            sess.delete(asset)


@cli.command()
@click.option('--config', metavar='FILE', help='Read format config from FILE.')
@click.option('--output', metavar='FILE', help='Save export zip to FILE.')
@click.option('--hide-tags', multiple=True, metavar='REGEXP [REGEXP...]',
              help='Exclude tags matching REGEXP from exported items.')
@click.option('--hide-datetime-tags', default=False, is_flag=True,
              help='Include tags related to timestamp data.')
@click.option('--hide-metadata-tags', default=False, is_flag=True,
              help='Include tags from media metadata like EXIF.')
@click.option('--hide-omnipresent-tags', default=False, is_flag=True,
              help='Do not remove tags that are present in all items.')
@click.argument('query', nargs=-1)
@click.pass_context
def export(ctx, query, config, **kwargs):
    '''Export a zip file matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    with open(config) as handle:
        formats = json.load(handle)['formats']
    with db.transaction() as sess:
        all_tags = sess.query(db.Tag).all()
        assets = db.Asset.matching(sess, ' '.join(query))
        count = importexport.export(assets, all_tags, formats, **kwargs)
        click.echo('Exported {} assets to {}'.format(
            click.style(str(count), fg='cyan'),
            click.style(kwargs['output'], fg='red')))


@cli.command('import')
@click.option('--tag', multiple=True, metavar='TAG [TAG...]',
              help='Add TAG to all imported items.')
@click.option('--path-tags', default=0, metavar='N',
              help='Add N parent directories as tags.')
@click.argument('source', nargs=-1)
@click.pass_context
def import_(ctx, source, tag, path_tags):
    '''Import assets into the database.

    If any source is a directory, all assets under that directory will be
    imported recursively.
    '''
    for path in importexport.walk(source):
        try:
            with db.transaction() as sess:
                asset = importexport.import_asset(sess, path, tags, path_tags)
            if asset:
                tasks.compute_hashes(asset)
        except KeyboardInterrupt:
            break
        except:
            logging.exception(f'! Error importing {path}')


@cli.command()
@click.option('--stamp', type=str,
              help='Modify the timestamp of matching records.')
@click.option('--add-tag', type=str, multiple=True, metavar='TAG [TAG...]')
@click.option('--remove-tag', type=str, multiple=True, metavar='TAG [TAG...]')
@click.option('--add-path-tags', default=0, metavar='N',
              help='Add N parent directories as tags.')
@click.argument('query', nargs=-1)
@click.pass_context
def modify(ctx, query, stamp, add_tag, remove_tag, add_path_tags):
    '''Modify assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.

    Common tasks are adding or removing tags, or updating the timestamps
    associated with one or more assets (e.g., to adjust for a
    miscalibrated camera or the like).

    The --stamp option can take two different types of timestamp specifiers.
    If this option is passed a timestamp string, it will replace the current
    timestamp for all matching assets. Otherwise it can contain any number of
    strings of the form 'sNx' which will adjust timestamp unit x by N units
    later (if s is '+') or earlier (if s is '-'). For example, '+3y,-2h' will
    shift the timestamp of all matching media three years later and two hours
    earlier. Here x can be 'y' (year), 'm' (month), 'd' (day), or 'h' (hour).
    '''
    with db.transaction() as sess:
        for asset in db.Asset.matching(sess, ' '.join(query)):
            for tag in add_tag:
                asset.add_tag(tag)
            for tag in remove_tag:
                asset.remove_tag(tag)
            if add_path_tags > 0:
                components = os.path.dirname(asset.path).split(os.sep)[::-1]
                for i in range(min(len(components) - 1, add_path_tags)):
                    asset.tags.add(components[i])
            if stamp:
                asset.update_stamp(stamp)
            sess.add(asset)


@cli.command()
@click.option('--config', metavar='FILE',
              help='Config FILE for thumbnailed media content.')
@click.option('--overwrite/--no-overwrite', default=False,
              help='When set, overwrite existing thumbnails.')
@click.argument('query', nargs=-1)
@click.pass_context
def thumbnail(ctx, query, config, overwrite):
    '''Create thumbnails for assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    with open(config) as handle:
        config = json.load(handle)
    with db.transaction() as sess:
        for asset in db.Asset.matching(sess, ' '.join(query)):
            for fmt in config['formats']:
                if fmt.get('medium', '').lower() == asset.medium.name.lower():
                    root = config['root']
                    if 'path' in fmt:
                        root = os.path.join(root, fmt['path'])
                    output = asset.export(fmt=_to_format(fmt['format']),
                                          root=root, overwrite=overwrite)
                    click.echo('{} {} -> {}'.format(click.style('*', fg='cyan'),
                                                    click.style(asset.path, fg='red'),
                                                    output))


@cli.command()
@click.option('--host', default='localhost', metavar='HOST',
              help='Run server on HOST.')
@click.option('--port', default=5555, metavar='PORT',
              help='Run server on PORT.')
@click.option('--debug/--no-debug', default=False)
@click.option('--hide-originals/--no-hide-originals', default=False)
@click.option('--thumbnails', metavar='FILE',
              help='Config FILE for thumbnailed media content.')
@click.pass_context
def serve(ctx, host, port, debug, hide_originals, thumbnails):
    '''Start an HTTP server for asset metadata.'''
    from .serve import app
    from .serve import sql
    app.config['SQLALCHEMY_ECHO'] = debug
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + ctx.obj["db_path"]
    app.config['hide-originals'] = hide_originals
    with open(thumbnails) as handle:
        app.config['thumbnails'] = json.load(handle)
    sql.init_app(app)
    app.run(host=host, port=port, debug=debug, threaded=False, processes=8)
