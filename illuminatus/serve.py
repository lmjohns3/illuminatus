import contextlib
import flask
import os
import shutil
import tempfile

from flask import request

from . import importexport
from . import tools

app = flask.Flask('illuminatus')


@contextlib.contextmanager
def get_item(id):
    for item in app.config['db'].select_by_id(id):
        yield item


@app.route('/tags')
def tags():
    return flask.jsonify(
        tags=[t._asdict() for t in sorted(app.config['db'].tags)])


@app.route('/sizes')
def sizes():
    return flask.jsonify(sizes=app.config['sizes'])


@app.route('/query/<string:query>')
def query(query):
    kwargs = dict(order=request.args.get('order', 'stamp-'),
                  offset=int(request.args.get('offset', 0)),
                  limit=int(request.args.get('limit', 0)))
    return flask.jsonify(
        items=[m.rec for m in app.config['db'].select(query, **kwargs)])


@app.route('/export/<string:query>', methods=['POST'])
def export(query):
    db = app.config['db']
    dirname = tempfile.mkdtemp()
    output = os.path.join(dirname, request.form['name'] + '.zip')
    sizes = [int(x) for x in request.form.get('sizes', '1000').split()]

    importexport.Exporter(db.tags, db.select(query)).run(
        output=output,
        sizes=sizes,
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


@app.route('/item/<int:id>/', methods=['PUT'])
def update_item(id):
    stamp = request.form.get('stamp', '')
    add_tags = request.form.get('add_tags', '').split()
    remove_tags = request.form.get('remove_tags', '').split()
    with get_item(id) as item:
        for tag in add_tags:
            item.add_tag(tag)
        for tag in remove_tags:
            item.remove_tag(tag)
        if stamp:
            item.update_stamp(stamp)
        item.save()
        return flask.jsonify(item.rec)


@app.route('/item/<int:id>/', methods=['DELETE'])
def delete_item(id):
    with get_item(id) as item:
        item.delete(hide_original=app.config['hide-originals'])
        return flask.jsonify('ok')


@app.route('/item/<int:id>/filters/<string:filter>', methods=['POST'])
def add_filter(id, filter):
    kwargs = dict(filter=filter)
    for arg in tools.FILTER_ARGS[filter].split():
        kwargs[arg] = float(request.form[arg])
    with get_item(id) as item:
        item.add_filter(kwargs)
        item.save()
        root = app.config['db'].root
        for s in app.config['sizes']:
            item.thumbnail(s, root)
        return flask.jsonify(item.rec)


@app.route('/item/<int:id>/filters/<string:filter>/<int:index>', methods=['DELETE'])
def delete_filter(id, filter, index):
    with get_item(id) as item:
        item.remove_filter(filter, index)
        item.save()
        root = app.config['db'].root
        for s in app.config['sizes']:
            item.thumbnail(s, root)
        return flask.jsonify(item.rec)


@app.route('/')
def index():
    return app.send_static_file('editing.html')


@app.route('/thumb/<path:path>')
def thumb(path):
    return flask.send_from_directory(app.config['db'].root, path)
