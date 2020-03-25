import click
import re
import sqlalchemy

from . import db


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)

    # Regular expression matchers for different "groups" of tags. The order here
    # is used to sort the tags on an asset. Tags not matching any of these
    # groups are "user-defined" and will sort before or after these.
    PATTERNS = (
        # Year.
        r'(19|20)\d\d',

        # Month.
        'january', 'february', 'march', 'april', 'may', 'june', 'july',
        'august', 'september', 'october', 'november', 'december',

        # Day of month.
        r'\d(st|nd|rd|th)', r'\d\d(st|nd|rd|th)',

        # Day of week.
        'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',

        # Time of day.
        r'12am', r'\dam', r'\d\dam', r'12pm', r'\dpm', r'\d\dpm',

        # Camera.
        r'kit:\S+',

        # Aperture.
        r'ƒ-\d', r'ƒ-\d\d', r'ƒ-\d\d\d',

        # Focal length.
        r'\dmm', r'\d\dmm', r'\d\d\dmm', r'\d\d\d\dmm',

        # Geolocation.
        r'country:\S+', r'state:\S+', r'city:\S+', r'place:\S+',

        # User-defined: everything else.
        r'.*',
    )

    def __repr__(self):
        colors = ('red', 'yellow', 'green', 'cyan', 'blue', 'magenta')
        color = colors[self.pattern % len(colors)]
        return click.style(f' {self.name} ', bg=color, fg='black')

    @property
    def pattern(self):
        for i, pattern in enumerate(Tag.PATTERNS):
            if pattern == self.name or re.match(pattern, self.name):
                return i
        return -1

    def to_dict(self):
        return dict(id=self.id, name=self.name)


class Label(db.Model):
    __tablename__ = 'labels'

    id = db.Column(db.Integer, primary_key=True)

    source = db.Column(db.String)
    score = db.Column(db.Float, nullable=False)
    yeas = db.Column(db.Integer, nullable=False, default=0)
    nays = db.Column(db.Integer, nullable=False, default=0)

    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id', ondelete='CASCADE'),
                         nullable=False)
    asset = sqlalchemy.orm.relationship('Asset', backref='labels', lazy='select')

    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'),
                       nullable=False)
    tag = sqlalchemy.orm.relationship('Tag', backref='labels', lazy='select')
