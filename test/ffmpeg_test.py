from util import *


@pytest.mark.parametrize('filters', [
    [],
    [dict(filter='rotate', degrees=10)],
    [dict(filter='crop', x1=0.1, y1=0.1, x2=0.8, y2=0.8)],
    [dict(filter='saturation', percent=110)],
    [dict(filter='brightness', percent=90)],
    [dict(filter='autocontrast', percent=10)],
    [dict(filter='hue', degrees=90)],
    [dict(filter='vflip')],
    [dict(filter='hflip')],
])
def test_video_filters(sess, tmpdir, filters):
    video = sess.query(Asset).get(VIDEO_ID)
    video.update_from_metadata()
    for filter in filters:
        video.add_filter(filter)

    root = tmpdir.mkdir('export')
    assert root.listdir() == []
    video.export(str(root), ext='mp4')
    assert sorted(root.listdir()) == [str(root.join(f'{video.slug}.mp4'))]


@pytest.mark.parametrize('filters', [
    [],
    [dict(filter='rotate', degrees=10)],
    [dict(filter='crop', x1=0.1, y1=0.1, x2=0.8, y2=0.8)],
    [dict(filter='saturation', percent=110)],
    [dict(filter='brightness', percent=90)],
    [dict(filter='contrast', percent=90)],
    [dict(filter='autocontrast', percent=1)],
    [dict(filter='hue', degrees=90)],
    [dict(filter='vflip')],
    [dict(filter='hflip')],
])
def test_photo_filters(sess, tmpdir, filters):
    photo = sess.query(Asset).get(PHOTO_ID)
    photo.update_from_metadata()
    for filter in filters:
        photo.add_filter(filter)

    root = tmpdir.mkdir('export')
    assert root.listdir() == []
    photo.export(str(root), ext='jpg')
    assert sorted(root.listdir()) == [str(root.join(f'{photo.slug}.jpg'))]
