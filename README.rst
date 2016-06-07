illuminatus
===========

A Python library and command line tool for managing visual digital media (photos
and videos) using sqlite, pillow, and ffmpeg.

Command-line
============

The package comes with a command-line script, ``illuminatus``, that serves as a
command-line frontend to many of the features provided by the library. To get
help, just invoke the script::

  illuminatus

The script requires an operation to be specified; the operations provided by the
script are documented in more detail below, but first a word about databases.

Specifying a database
---------------------

To allow the script to do something useful, you'll need to provide the location
of a database holding media metadata. You can do this in one of two ways:

- Provide the ``--db`` flag when running the script.
- Specify a database location using the ``ILLUMINATUS_DB`` environment
  variable.

If both are provided, the flag overrides the setting of the environment
variable.

Importing
---------

The ``illuminatus`` script can recursively import media from any filesystem
path.

::

  illuminatus import ~/Pictures

Exporting
---------

The ``illuminatus`` script can export media that are tagged in a specific way.
The export comes in a zip file and includes a metadata dump of the relevant tags
and such.

::

  illuminatus export

Listing
-------

The ``illuminatus`` script can show items in the database that match certain
queries.

::

  illuminatus list

Tagging
-------

The ``illuminatus`` script can add or remove tags to or from media.

::

  illuminatus retag

Thumbnails
----------

The ``illuminatus`` script can regenerate the thumbnails for existing items in
the database.

::

  illuminatus rethumb

Serving
-------

The ``illuminatus`` script can provide a RESTful HTTP server (using
`bottle.py`_) for media data and metadata.

::

  illuminatus serve

.. _bottle.py: http://bottlepy.org

Library
=======

