As-Is Server
============
Twisted comes with a feature called `as-is` serving, inspired by Apache. But,
who wants to include Twisted as a dependency?

This is based on `bottle`, and thus supports a number of WSGI backends 
(including Twisted and gevent), and is meant to be lightweight.

Installation
============
Easy peasy:

    sudo pip install asis

Or for those who prefer from source:

    git clone https://github.com/seomoz/asis
    cd asis && sudo python setup.py install

Usage
=====
You can run an `asis` server relatively easily:

    import asis
    # Serve files stored in 'foo/' on port 8080
    server = asis.Server('foo', 8080)
    server.run()

    ...

    server.stop()

Alternatively, it can be used in a context-manager fashion:

    import asis
    import requests

    with asis.Server('foo') as server:
        requests.get('http://localhost:8080/foo/bar.asis')

There's also a command-line utility included for convenience for serving asis
files as a standalone server, which is especially helpful for seeing these
files through `curl` or the browser:

    # Serve files out of 'foo/' on port 8080
    asis-server foo --port 8080
    # Same, using gevent and being verbose
    asis-server foo --port 8080 --server gevent --verbose

Contributing
============
Questions, comments, ideas always welcome.
