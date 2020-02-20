import arrow
import collections
import contextlib
import flask
import flask_socketio
import flask_sqlalchemy
import os
import shutil
import tempfile

from . import db
from . import importexport
from . import metadata
from . import tools

app = flask.Flask('illuminatus')
sql = flask_sqlalchemy.SQLAlchemy()
socketio = flask_socketio.SocketIO(app)


def _get_asset(id):
    return sql.session.query(db.Asset).get(id)


@socketio.on('foo event')
def handle_foo_event(json):
    return 'a'


@app.route('/api/query/<string:query>/')
def assets(query):
    req = flask.request
    order = req.args.get('order', 'stamp')
    assets = (db.Asset.matching(sql.session, query, order=order)
              .limit(int(req.args.get('limit', 0)))
              .offset(int(req.args.get('offset', 0))))
    return flask.jsonify(assets=[a.to_dict() for a in assets])


@app.route('/api/export/<string:query>/', methods=['POST'])
def export(query):
    req = flask.request
    formats = {
        '{}_format'.format(medium): metadata.Format.parse(req.form[medium])
        for medium in ('audio', 'photo', 'video')}

    db = app.config['db']
    dirname = tempfile.mkdtemp()
    importexport.Exporter(db.tags, db.select(query), **formats).run(
        output=os.path.join(dirname, req.form['name'] + '.zip'),
        hide_tags=req.form.get('hide_tags', '').split(),
        hide_metadata_tags=req.form.get('hide_metadata_tags', '') == '1',
        hide_datetime_tags=req.form.get('hide_datetime_tags', '') == '1',
        hide_omnipresent_tags=req.form.get('hide_omnipresent_tags', '1') == '1',
    )

    @flask.after_this_request
    def cleanup(response):
        shutil.rmtree(dirname)
        return response

    return flask.send_file(output, as_attachment=True)


@app.route('/api/asset/<int:id>/', methods=['PUT'])
def update_asset(id):
    req = flask.request
    stamp = req.form.get('stamp', '')
    add_tags = req.form.get('add_tags', '').split()
    remove_tags = req.form.get('remove_tags', '').split()
    asset = _get_asset(id)
    for tag in add_tags:
        asset.add_tag(tag)
    for tag in remove_tags:
        asset.remove_tag(tag)
    if stamp:
        asset.update_stamp(stamp)
    asset.save()
    return flask.jsonify(asset.to_dict())


@app.route('/api/asset/<int:id>/', methods=['DELETE'])
def delete_asset(id):
    _get_asset(id).delete(hide_original=app.config['hide-originals'])
    return flask.jsonify('ok')


@app.route('/api/asset/<int:id>/filters/<string:filter>/', methods=['POST'])
def add_filter(id, filter):
    req = flask.request
    kwargs = dict(filter=filter)
    for arg in tools.FILTER_ARGS[filter].split():
        kwargs[arg] = float(req.form[arg])
    asset = _get_asset(id)
    asset.add_filter(kwargs)
    asset.save()
    root = app.config['db'].root
    for s in app.config['sizes']:
        asset.export(s, root, force=True)
    return flask.jsonify(asset.to_dict())


@app.route('/api/asset/<int:id>/filters/<string:filter>/<int:index>/', methods=['DELETE'])
def delete_filter(id, filter, index):
    asset = _get_asset(id)
    asset.remove_filter(filter, index)
    asset.save()
    root = app.config['db'].root
    for s in app.config['sizes']:
        asset.export(s, root, force=True)
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


@app.route('/')
@app.route('/view/<int:id>/')
@app.route('/edit/<int:id>/')
@app.route('/label/<int:id>/')
@app.route('/cluster/<int:id>/')
@app.route('/browse/<string:query>/')
def index(*args, **kwargs):
    return flask.render_template('index.html')
