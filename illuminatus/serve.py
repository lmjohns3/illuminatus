import contextlib
import datetime
import flask
import flask_sqlalchemy
import io
import os
import shutil
import tempfile

from flask import request

from .db import matching_assets
from . import importexport
from .media import Asset, Tag
from . import tools

app = flask.Flask('illuminatus')
db = flask_sqlalchemy.SQLAlchemy()


@contextlib.contextmanager
def get_asset(id):
    for asset in app.config['db'].select_by_id(id):
        yield asset


@app.route('/query/<string:query>')
def query(query):
    order = request.args.get('order', 'stamp-')
    assets = (matching_assets(db.session, query, order=order)
              .limit(int(request.args.get('limit', 0)))
              .offset(int(request.args.get('offset', 0))))
    return flask.jsonify(assets=[a.to_dict() for a in assets])


@app.route('/export/<string:query>', methods=['POST'])
def export(query):
    formats = {'{}_format'.format(medium): Format.parse(request.form[medium])
               for medium in ('audio', 'photo', 'video')}

    db = app.config['db']
    dirname = tempfile.mkdtemp()
    importexport.Exporter(db.tags, db.select(query), **formats).run(
        output=os.path.join(dirname, request.form['name'] + '.zip'),
        hide_tags=request.form.get('hide_tags', '').split(),
        hide_metadata_tags=request.form.get('hide_metadata_tags') == '1',
        hide_datetime_tags=request.form.get('hide_datetime_tags') == '1',
        hide_omnipresent_tags=request.form.get('hide_omnipresent_tags') == '1',
    )

    @flask.after_this_request
    def cleanup(response):
        shutil.rmtree(dirname)
        return response

    return flask.send_file(output, as_attachment=True)


@app.route('/asset/<int:id>/', methods=['PUT'])
def update_asset(id):
    stamp = request.form.get('stamp', '')
    inc_tags = request.form.get('inc_tags', '').split()
    dec_tags = request.form.get('dec_tags', '').split()
    remove_tags = request.form.get('remove_tags', '').split()
    with get_asset(id) as asset:
        for tag in inc_tags:
            asset.increment_tag(tag)
        for tag in dec_tags:
            asset.decrement_tag(tag)
        for tag in remove_tags:
            asset.remove_tag(tag)
        if stamp:
            asset.update_stamp(stamp)
        asset.save()
        return flask.jsonify(asset.rec)


@app.route('/asset/<int:id>/', methods=['DELETE'])
def delete_asset(id):
    with get_asset(id) as asset:
        asset.delete(hide_original=app.config['hide-originals'])
        return flask.jsonify('ok')


@app.route('/asset/<int:id>/filters/<string:filter>', methods=['POST'])
def add_filter(id, filter):
    kwargs = dict(filter=filter)
    for arg in tools.FILTER_ARGS[filter].split():
        kwargs[arg] = float(request.form[arg])
    with get_asset(id) as asset:
        asset.add_filter(kwargs)
        asset.save()
        root = app.config['db'].root
        for s in app.config['sizes']:
            asset.export(s, root, force=True)
        return flask.jsonify(asset.rec)


@app.route('/asset/<int:id>/filters/<string:filter>/<int:index>', methods=['DELETE'])
def delete_filter(id, filter, index):
    with get_asset(id) as asset:
        asset.remove_filter(filter, index)
        asset.save()
        root = app.config['db'].root
        for s in app.config['sizes']:
            asset.export(s, root, force=True)
        return flask.jsonify(asset.rec)


@app.route('/config')
def config():
    return flask.jsonify(
        formats=app.config['formats'],
        tags=Tag.with_asset_counts(db.session),
    )


@app.route('/thumb/<path:path>')
def thumb(path):
    return flask.send_from_directory(app.config['thumbnails'], path)


@app.route('/')
def index():
    return flask.render_template('editing.html', now=datetime.datetime.now())
    #return app.send_static_file('editing.html')
