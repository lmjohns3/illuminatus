import flask
# import flask_socketio
import flask_sqlalchemy
import glob
import json
import os
import re
import shutil
import sqlalchemy
import tempfile
import yaml

from . import assets
from . import celery
from . import importexport
from . import tags

from .query import assets as matching_assets

app = flask.Flask('illuminatus')
sql = flask_sqlalchemy.SQLAlchemy()


def _get_asset(slug):
    return sql.session.query(assets.Asset).filter(
        assets.Asset.slug.startswith(slug)).one()


def _json(items):
    return flask.jsonify([item.to_dict() for item in items])


# socketio = flask_socketio.SocketIO(app)
# @socketio.on('foo event')
# def handle_foo_event(json):
#     return 'a'


@app.route('/query/<path:query>')
def query(query):
    get = flask.request.args.get
    return _json(matching_assets(sql.session,
                                 query.split('/'),
                                 order=get('ord', 'stamp'),
                                 limit=int(get('lim', 99999)),
                                 offset=int(get('off', 0))).all())


@app.route('/export/<path:query>', methods=['POST'])
def export(query):
    get = flask.request.form.get
    dirname = tempfile.mkdtemp()

    importexport.Exporter(
        matching_assets(sql.session, query.split('/')),
        json.loads(get('formats')),
    ).run(
        output=os.path.join(dirname, f'{get("name").zip}'),
        hide_tags=get('hide_tags', '').split(),
        hide_metadata_tags=get('hide_metadata_tags', '') == '1',
        hide_datetime_tags=get('hide_datetime_tags', '') == '1',
        hide_omnipresent_tags=get('hide_omnipresent_tags', '1') == '1',
    )

    @flask.after_this_request
    def cleanup(response):
        shutil.rmtree(dirname)
        return response

    return flask.send_file(output, as_attachment=True)


@app.route('/asset/<string:slug>/', methods=['GET'])
def get_asset(slug):
    return flask.jsonify(_get_asset(slug).to_dict())


@app.route('/asset/<string:slug>/', methods=['PUT'])
def update_asset(slug):
    asset = _get_asset(slug)
    stamp = flask.request.json.get('stamp', '')
    if stamp:
        asset.update_stamp(stamp)
        asset.tags.discard('untouched')
        sql.session.commit()
    return flask.jsonify(asset.to_dict())


@app.route('/asset/<string:slug>/', methods=['DELETE'])
def delete_asset(slug):
    asset = _get_asset(slug)

    trash = app.config.get('trash')
    if trash and os.path.isdir(trash) and os.path.exists(asset.path):
        asset.move_to_trash(trash)

    # Clean up any thumbnails for this asset.
    thumbs = app.config['thumbnails']
    for fn in glob.glob(asset.path_for_export(thumbs, '*', '*')):
        os.unlink(fn)

    sql.session.delete(asset)
    sql.session.commit()
    return flask.jsonify('ok')


@app.route('/asset/<string:slug>/read/<string:fmt>/')
def read(slug, fmt):
    motion = flask.request.args.get('m', '0')
    asset = _get_asset(slug)
    ext = app.config['formats'][asset.medium][fmt].get('ext')
    if asset.medium == 'video' and motion == '0':
        ext = 'png'
    try:
        return flask.send_file(
            asset.path_for_export(app.config['thumbnails'], fmt, ext))
    except FileNotFoundError:
        flask.abort(404)


@app.route('/asset/<string:slug>/similar/tag/', methods=['GET'])
def get_similar_assets_by_tag(slug):
    return _json(_get_asset(slug).similar_by_tag(
        sql.session,
        min_sim=float(flask.request.args.get('min', 0.5)),
        limit=int(flask.request.args.get('lim', 99999))))


@app.route('/asset/<string:slug>/similar/content/', methods=['GET'])
def get_similar_assets_by_content(slug):
    return _json(_get_asset(slug).similar_by_content(
        sql.session,
        method=flask.request.args.get('alg', 'diff-8'),
        max_distance=int(flask.request.args.get('max', 1))))


@app.route('/asset/<string:slug>/tags/<string:tag>/', methods=['POST'])
def add_tag(slug, tag):
    asset = _get_asset(slug)
    name = tags.Tag.canonical_form(tag)
    if name:
        tag = sql.session.query(tags.Tag).filter(tags.Tag.name == name).scalar()
        if not tag:
            tag = tags.Tag(name=name)
            sql.session.add(tag)
        asset._tags.add(tag)
        asset.tags.discard('untouched')
        sql.session.add(asset)
        sql.session.commit()
    return flask.jsonify(asset.to_dict())


@app.route('/asset/<string:slug>/tags/<string:tag>/', methods=['DELETE'])
def remove_tag(slug, tag):
    asset = _get_asset(slug)
    tag = sql.session.query(tags.Tag).filter(
        tags.Tag.name == tags.Tag.canonical_form(tag)).scalar()
    if tag:
        asset._tags.remove(tag)
        asset.tags.discard('untouched')
        sql.session.add(asset)
        sql.session.commit()
    return flask.jsonify(asset.to_dict())


FILTER_ARGS = dict(
    autocontrast='percent',
    brightness='percent',
    contrast='percent',
    crop='x1 x2 y1 y2',
    hflip='',
    hue='degrees',
    rotate='degrees',
    saturation='percent',
    trim='',
    vflip='',
)


@app.route('/asset/<string:slug>/filters/<string:filter>/', methods=['POST'])
def add_filter(slug, filter):
    kwargs = dict(filter=filter)
    for arg in FILTER_ARGS[filter].split():
        kwargs[arg] = float(flask.request.form[arg])
    asset = _get_asset(slug)
    asset.add_filter(kwargs)
    for path, kwargs in app.config['formats'][asset.medium].items():
        kw = dict(slug=asset.slug,
                  dirname=app.config['thumbnails'],
                  overwrite=True)
        kw.update(kwargs)
        celery.export.apply_async(kwargs=kw, queue=asset.medium)
    return flask.jsonify(asset.to_dict())


@app.route('/asset/<string:slug>/filters/<string:filter>/<int:index>/',
           methods=['DELETE'])
def remove_filter(slug, filter, index):
    asset = _get_asset(slug)
    asset.remove_filter(filter, index)
    for path, kwargs in app.config['formats'][asset.medium].items():
        kw = dict(slug=asset.slug,
                  dirname=app.config['thumbnails'],
                  overwrite=True)
        kw.update(kwargs)
        celery.export.apply_async(kwargs=kw, queue=queue)
    return flask.jsonify(asset.to_dict())


@app.route('/manifest.json')
def manifest():
    return flask.jsonify(dict(
        short_name='Awww',
        name='Illuminatus',
        icons=[dict(src='icon.png', sizes='192x192', type='image/png')],
        start_url='/',
        display='standalone',
        orientation='portrait',
    ))


def _annotate_tags(counts, groups):
    '''For each tag in the db, annotate it with metadata from config.'''
    for tag in sql.session.query(tags.Tag).all():
        name = tag.name
        tag = dict(name=name, count=counts.get(tag.id, 0))
        for g, group in enumerate(groups):
            for p, patt in enumerate(group['patterns']):
                if name == patt or re.fullmatch(patt, name):
                    tag['group'] = group['group']
                    tag['icon'] = group['icon']
                    tag['order'] = f'{g + 1:03d}{p + 1:06d}'
                    tag['hue'] = group.get('hue', 0)
                    if group.get('editable'):
                        tag['editable'] = True
                    break
            if 'order' in tag:
                break
        yield tag


@app.route('/tags/')
def config():
    with open(app.config['config']) as handle:
        parsed = yaml.load(handle, Loader=yaml.CLoader)

    default_group = dict(group='other', icon='🏷️', patterns=['.*'], editable=True)
    groups = parsed.get('tags', []) + [default_group]

    # Get tag counts by grouping the asset-tag secondary table.
    aid, tid = assets.asset_tags.c.asset_id, assets.asset_tags.c.tag_id
    counts = dict(sql.session.query(tid, sqlalchemy.func.count(aid)).group_by(tid))

    return flask.jsonify(dict(tags=list(_annotate_tags(counts, groups))))


@app.route('/')
@app.route('/<path:path>')
def index(*args, **kwargs):
    return flask.render_template('index.html')
