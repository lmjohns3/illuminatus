import argparse
import collections
import lmj.cli
import lmj.photos
import os
import sys

cmd = lmj.cli.add_command('export')
cmd.add_argument('--target', default=os.curdir, metavar='DIR',
                 help='export photos to pages rooted at DIR')
cmd.add_argument('--require', nargs='+', metavar='TAG',
                 help='only export photos with this tag')
cmd.add_argument('--replace', action='store_true',
                 help='replace existing exported photos')
cmd.add_argument('--preserve-omnipresent-tags', action='store_true',
                 help='do not remove tags that are present in all photos')
cmd.add_argument('tag', nargs=argparse.REMAINDER,
                 help='export photos with these tags')
cmd.set_defaults(mod=sys.modules[__name__])


PAGE = u'''\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link href="//netdna.bootstrapcdn.com/bootstrap/3.0.0/css/bootstrap.min.css" rel="stylesheet">
<link href="//netdna.bootstrapcdn.com/font-awesome/3.2.1/css/font-awesome.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/fancybox/2.1.5/jquery.fancybox.css" rel="stylesheet">
<style>
body {{ background: #333; }}
#tags {{ margin: 10px 0; }}
.thumbnail {{ background: #111; border-color: #222; margin-bottom: 10px; }}
.tag {{ color: #ccc; border: solid 1px #ccc; padding: 2px 5px; }}
.tag.alive {{ background: #ccc; color: #111; border-color: #111; }}
</style>
<title>Photos: {tag}</title>
<body>
<div class="container">
<div class="row"><div id="tags" class="col-xs-12">{tags}</div></div>
<div class="row">{images}</div>
</div>
<script src="//ajax.googleapis.com/ajax/libs/jquery/1.10.0/jquery.min.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/fancybox/2.1.5/jquery.fancybox.pack.js"></script>
<script>
toggles = {{}};

$(function() {{
  $('.thumbnail').fancybox();

  $('#tags').on('click', '.tag', function(e) {{
    var elem = $(e.target);
    name = elem.html();
    if (toggles[name]) {{
      delete toggles[name];
      elem.removeClass('alive');
    }} else {{
      toggles[name] = true;
      elem.addClass('alive');
    }}
  }});
}})</script>
</body>
</html>
'''

TAG = u'<a href="#" class="img-rounded tag">{name}</a> '

IMAGE = u'''\
<div class="col-md-2 col-sm-3 col-xs-4">\
<a class="thumbnail" data-fancybox-group="gallery" data-tags="{tags}" href="{image}">\
<img class="img-rounded" src="{thumbnail}"></a>\
</div>
'''


def export(args, tag):
    # pull matching photos from the database.
    images = list(lmj.photos.find_many(tags=[tag] + (args.require_tag or [])))

    # count tag usage for this set of photos.
    tag_counts = collections.defaultdict(int)
    for p in images:
        for t in p.tag_set:
            tag_counts[t] += 1

    if not args.preserve_omnipresent_tags:
        # remove tags from the union that are applied to all photos in this set.
        omnipresent = [t for t, c in tag_counts.iteritems() if c == len(images)]
        for t in omnipresent:
            del tag_counts[t]

    # export the individual photo images.
    for p in images:
        p.make_thumbnails(args.target, replace=args.replace)

    # write out some html to show the photos.
    with open(os.path.join(args.target, tag + '.html'), 'w') as out:
        out.write(
            PAGE.format(
                tag=tag,
                tags=u''.join(
                    TAG.format(name=t)
                    for t in sorted(tag_counts)),
                images=u''.join(
                    IMAGE.format(
                        tags=u' '.join(p.tag_set),
                        image='full/' + p.thumb_path,
                        thumbnail='thumb/' + p.thumb_path)
                    for p in images)).encode('utf-8'))


def main(args):
    for tag in args.tag:
        export(args, tag)
