import datetime
import lmj.cli
import lmj.photos
import os
import sys

cmd = lmj.cli.add_command('import')
cmd.add_argument('--thumbs', default=os.curdir, metavar='DIR',
                 help='store image thumbnails under DIR')
cmd.add_argument('source', nargs='+', metavar='PATH',
                 help='import photos from these PATHs')
cmd.set_defaults(mod=sys.modules[__name__])


def exists(path):
    with lmj.photos.connect() as db:
        sql = 'SELECT COUNT(path) FROM photo WHERE path = ?'
        c, = db.execute(sql, (path, )).fetchone()
        return c > 0


def import_one(path, thumbs):
    exif, = lmj.photos.parse(subprocess.check_output(['exiftool', '-json', path]))

    stamp = datetime.datetime.now()
    for key in 'DateTimeOriginal CreateDate ModifyDate FileModifyDate'.split():
        stamp = exif.get(key)
        if stamp:
            stamp = datetime.datetime.strptime(stamp[:19], '%Y:%m:%d %H:%M:%S')
            break

    meta = dict(stamp=stamp, user_tags=[])

    photo = None
    with lmj.photos.connect() as db:
        db.execute('INSERT INTO photo (path) VALUES (?)', (path, ))
        sql = 'SELECT id, path, meta, exif, ops FROM photo WHERE path = ?'
        photo = lmj.photos.Photo(*db.execute(sql, (path, )).fetchone())
        photo.meta = meta
        photo.exif = exif

    photo.make_thumbnails(thumbs)
    photo.meta['thumb'] = photo.thumb_path

    # update the database with correct metadata.
    sql = 'UPDATE photo SET tags = ?, meta = ?, exif = ?, stamp = ? where id = ?'
    data = ('|%s|' % '|'.join(photo.tag_set),
            lmj.photos.stringify(meta),
            lmj.photos.stringify(exif),
            photo.stamp,
            photo.id)
    with lmj.photos.connect() as db:
        db.execute(sql, data)


def main(args):
    lmj.photos.DB = args.db
    for src in args.source:
        for base, dirs, files in os.walk(src):
            dots = [n for n in dirs if n.startswith('.')]
            [dirs.remove(d) for d in dots]
            for name in files:
                if name.startswith('.'):
                    continue
                _, ext = os.path.splitext(name)
                if ext.lower()[1:] in 'gif jpg jpeg png tif tiff':
                    path = os.path.join(base, name)
                    if exists(path):
                        print '=', path
                    else:
                        import_one(path, args.thumbs)
                        print '+', path
