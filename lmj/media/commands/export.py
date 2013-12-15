import argparse
import collections
import lmj.cli
import lmj.media
import os
import re
import sys

cmd = lmj.cli.add_command('export')
cmd.add_argument('--exclude', default=[], nargs='+', metavar='PATTERN',
                 help='do not export media tagged with PATTERN')
cmd.add_argument('--hide', default=[], nargs='+', metavar='PATTERN',
                 help='do not export info for tags matching PATTERN')
cmd.add_argument('--replace', default=False, action='store_true',
                 help='replace existing exported thumbnails, etc.')
cmd.add_argument('--require', default=[], nargs='+', metavar='TAG',
                 help='only export media tagged with TAG')
cmd.add_argument('--show-datetime-tags', default=False, action='store_true',
                 help='include tags related to date data')
cmd.add_argument('--show-exif-tags', default=False, action='store_true',
                 help='include tags related to EXIF data')
cmd.add_argument('--show-omnipresent-tags', default=False, action='store_true',
                 help='do not remove tags that are present in all media')
cmd.add_argument('--target', default=os.curdir, metavar='DIR',
                 help='export photos to pages rooted at DIR')
cmd.add_argument('tag', nargs=argparse.REMAINDER, metavar='TAG',
                 help='generate index page for this TAG')
cmd.set_defaults(mod=sys.modules[__name__])

logging = lmj.cli.get_logger('lmj.media.export')


PAGE = u'''\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link href="//netdna.bootstrapcdn.com/bootstrap/3.0.0/css/bootstrap.min.css" rel="stylesheet">
<link href="//cdnjs.cloudflare.com/ajax/libs/fancybox/2.1.5/jquery.fancybox.css" rel="stylesheet">
<link href="//fonts.googleapis.com/css?family=Source+Sans+Pro" rel="stylesheet">
<style>
body {{ background: #fff; }}
#tags {{ margin: 10px 0; }}
.tag {{ color: #fff; margin: 1px; padding: 2px 5px; cursor: pointer; opacity: 0.3; }}
.tag:hover {{ opacity: 0.7; }}
.tag.alive {{ opacity: 1.0; }}
.tag.date {{ background: #36c; }}
.tag.exif {{ background: #c33; }}
.tag.user {{ background: #393; }}
.thumb {{ margin: 10px 10px 0 0; text-align: center; max-width: 100%; }}
</style>
<title>Photos: {tag}</title>
<body>
<div class="container">
<div class="row"><h1 class="col-xs-12">{tag}</h1></div>
<div class="row"><ul id="tags" class="col-xs-12 list-unstyled">{tags}</ul></div>
<div class="row"><ul class="col-xs-12 list-unstyled">{pieces}</ul></div>
</div>
<script src="//ajax.googleapis.com/ajax/libs/jquery/2.0.2/jquery.min.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/fancybox/2.1.5/jquery.fancybox.pack.js"></script>
<script>
toggles = {{}};

function oz($elem, hide) {{
  var css = {{ left: 0, position: 'relative' }};
  var gallery = 'gallery';
  if (hide) {{
    css.left = -10000;
    css.position = 'absolute';
    gallery = 'hidden';
  }}
  $elem.closest('li').css(css);
  $elem.attr('data-fancybox-group', gallery);
}};

$(function() {{
  $('.fancybox').fancybox();

  $('#tags').on('click', '.tag', function(e) {{
    var $elem = $(e.target);
    var name = $elem.html();
    if (toggles[name]) {{
      delete toggles[name];
      $elem.removeClass('alive');
    }} else {{
      toggles[name] = true;
      $elem.addClass('alive');
    }}

    if (Object.keys(toggles).length === 0) {{
      $('.fancybox').each(function() {{ oz($(this), false); }});
    }} else {{
      var visible = '';
      for (name in toggles) {{
        if (visible !== '') visible += '|';
        visible += name;
      }}
      $('.fancybox').each(function() {{
        oz($(this), !$(this).attr('title').match(visible));
      }});
    }}
  }});
}});</script>
</body>
</html>
'''

TAG = u'<li class="img-rounded tag pull-left {class_}">{name}</li> '

PHOTO = u'''\
<li class="thumb pull-left">\
<a class="fancybox" data-fancybox-group="gallery" title="{title}" href="{image}">\
<img class="img-rounded" src="{thumbnail}"></a>\
</li>
'''


def filter_excluded(pieces, pattern):
    '''Omit pieces tagged with anything that matches the given pattern.'''
    logging.info('filtering out pieces matching %s', pattern)
    exclude = set()
    for p in pieces:
        for t in p.tag_set:
            if re.match(pattern, t):
                exclude.add(p.id)
                break
    return [p for p in pieces if p.id not in exclude]


MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
EXIF_TAG_RE = re.compile(r'^(f/[\d\.]+|\d+mm|\d+ms|iso:\d+|kit:.*)$')
DATE_TAG_RE = re.compile('^([12]\d{3}|\d+(st|nd|rd|th)|\d+[ap]m|[adefhimnorstuw]+day|(jan|febr)uary|march|april|may|june|july|august|(sept|nov|dec)ember|october)$')

def tag_class(tag):
    if DATE_TAG_RE.match(tag):
        return 'date'
    if EXIF_TAG_RE.match(tag):
        return 'exif'
    return 'user'

def tag_sort_key(tag):
    subgroup = ordinal = 0
    group = 2
    if EXIF_TAG_RE.match(tag):
        group = 1
    if DATE_TAG_RE.match(tag):
        group = 0
        if re.match(r'^\d+[ap]m$', tag):
            subgroup = 1 if tag.endswith('am') else 2
            ordinal = 0 if tag.startswith('12') else 1
            if re.match(r'^\d[ap]m$', tag):
                tag = '0' + tag
        elif re.match(r'^[adefhimnorstuw]+day$', tag):
            subgroup = 3
            ordinal = DAYS.index(tag)
        elif re.match(r'^\d+(st|nd|rd|th)$', tag):
            subgroup = 4
            if re.match('^\d\D', tag):
                tag = '0' + tag
        elif re.match(r'^[12]\d{3}$', tag):
            subgroup = 6
        else:
            subgroup = 5
            ordinal = '{:02d}'.format(MONTHS.index(tag))
    return '{}:{}:{}:{}'.format(group, subgroup, ordinal, tag)


def export(args, tag):
    logging.info('exporting %s ...', tag)

    # pull matching media pieces from the database.
    pieces = filter_excluded(
        list(lmj.media.db.find_tagged([tag] + args.require)),
        '^{}$'.format('|'.join(args.exclude)))

    logging.info('exporting %d pieces', len(pieces))

    # set up a function to get visible tags for a piece.
    hide_pattern = '^{}$'.format('|'.join(args.hide))
    logging.info('hiding tags matching %s', hide_pattern)
    def visible_tags(piece):
        ts = piece.user_tag_set
        if args.show_exif_tags:
            ts |= piece.exif_tag_set
        if args.show_datetime_tags:
            ts |= piece.datetime_tag_set
        return (t for t in ts if not re.match(hide_pattern, t))

    # count tag usage for this set of media.
    tag_counts = collections.defaultdict(int)
    for p in pieces:
        for t in visible_tags(p):
            tag_counts[t] += 1

    if not args.show_omnipresent_tags:
        # remove tags that are applied to all media pieces.
        omnipresent = [t for t, c in tag_counts.iteritems() if c == len(pieces)]
        for t in omnipresent:
            del tag_counts[t]
            hide_pattern = hide_pattern[:-1]
            if hide_pattern != '^':
                hide_pattern += '|'
            hide_pattern += t + '$'

    logging.info('%d unique tags', len(tag_counts))

    # export the individual media pieces.
    for p in pieces:
        logging.info('%s: exporting', p.thumb_path)
        #p.export(args.target, replace=args.replace)

    # write out some html to show the pieces.
    with open(os.path.join(args.target, tag + '.html'), 'w') as out:
        def title(p):
            return u', '.join(sorted(visible_tags(p), key=tag_sort_key))
        photo = lambda p: PHOTO.format(
            title=title(p),
            image='full/' + p.thumb_path,
            thumbnail='thumb/' + p.thumb_path)
        out.write(PAGE.format(
            tag=tag,
            tags=u''.join(TAG.format(name=t, class_=tag_class(t))
                          for t in sorted(tag_counts, key=tag_sort_key)),
            pieces=u''.join(photo(p) for p in pieces)).encode('utf-8'))


def main(args):
    if not os.path.isdir(args.target):
        os.makedirs(args.target)
    for tag in args.tag:
        export(args, tag)
