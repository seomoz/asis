As-Is Server
============
When it comes to unit testing tools that fetch HTTP resources, we decided we'd
like to have a way to easily store pre-determined responses, and then serve
them from a server in the same process as we're running these tests. No monkey
patching, no infrastructure (like a caching proxy server).

It should be mentioned that if you're looking to capture requests from existing
services and then replay them, the [vcr](https://github.com/myronmarston/vcr)
project has been ported to several languages and is very useful.

What Is?
========
Twisted comes with a feature called `as-is` serving, inspired by Apache. But,
who wants to include Twisted as a dependency?

This is based on `bottle`, and thus supports a number of WSGI backends 
(including Twisted and gevent), and is meant to be lightweight. An `as-is`
document is one in which both the headers and the content for an HTTP response
are stored:

    HTTP/1.0 200 OK
    Content-Length: 137
    Content-Type: text/html

    <html>
        <head>
            <title>Basic Test Page</title>
        </head>
        <body>
            <p>Hello, I'm a test page</p>
        </body>
    </html>

__Note__ that this requires only newlines for the headers -- the carriage
returns are added automatically for convenience.

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

Bells and Whistles
==================
There are few features you may need to take advantage of:

Content-Encoding
----------------
If you supply the `Content-Encoding` header as either `gzip` or `deflate`, the
plain contents stored in the file are compressed and sent over the wire that
way. In those cases, you can leave `Content-Length` as 0, and the true content
length (after compression) will be sent in its place. For example, the
following gets sent as gzip-compressed content correctly to the browser:

    HTTP/1.0 200 OK
    Content-Length: 0
    Content-Type: text/plain
    Content-Encoding: gzip

    Hello world!

Charset
-------
If you include a `charset` in your `Content-Type` header, then your content
will be interpreted as `utf-8` on disk, and then encoded in the provided
encoding. The idea is to help the editing process so that you don't have to
explicitly save your examples in their declared character set. Like changes to
`Content-Encoding`, the `Content-Length` header is recomputed to be correct
once the transformation is complete.

Modes
=====
By default, the server is started with the `gevent` server, and it's started in
a background green thread, and it supposed to be ready to serve requests as
soon as `run()` returns.

Alternatively, the server can be started in two other modes, `fork` and
`block`. If `fork`, then it will run the server in a separate process, and it
still works as both a context manager and after calling `run()`. If `block` is
selected, then it runs in a blocking way. For example:

    # Run it in a separate process
    with asis.Server('foo', port=8080, mode='fork'):
        # Make some requests
        ...

Examples and Tests
==================
Included in here are a number of examples of as-is documents, and `test.py` can
be run directly to verify that they are transferred correctly:

    ./test.py

It also provides an example of how you might incorporate it into your unit
tests

Contributing
============
Questions, comments, ideas always welcome.
