import sqlalchemy
import sqlalchemy.ext.declarative

from sqlalchemy import Column, PrimaryKeyConstraint, Table
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String

Model = sqlalchemy.ext.declarative.declarative_base()


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    cur = dbapi_connection.cursor()
    cur.execute('PRAGMA encoding = "UTF-8"')
    cur.execute('PRAGMA foreign_keys = ON')
    cur.execute('PRAGMA journal_mode = WAL')
    cur.execute('PRAGMA synchronous = NORMAL')
    cur.close()


def engine(path, echo=False):
    return sqlalchemy.create_engine('sqlite:///' + path, echo=echo)


# Session gets bound to an engine in cli.py using db.Session.configure(...).
Session = sqlalchemy.orm.sessionmaker(autoflush=False)
