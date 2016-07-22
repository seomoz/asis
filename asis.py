#!/usr/bin/env python
#
# Copyright (c) 2012 SEOmoz
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

'''A server that merely serves as-is documents'''

import contextlib
import logging
import os
import re
import socket

from bottle import Bottle, run, response, abort


# Our logger
logger = logging.getLogger('asis')
formatter = logging.Formatter('[%(asctime)s] %(levelname)s : %(message)s')
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.WARNING)


class Handler(object):
    '''Handle requests for asis documents.'''

    # Regular expression for matching found headers
    headerMatch = re.compile(r'([^:]+):([^\r]+)$')
    supported_encodings = ('gzip', 'deflate')

    @staticmethod
    def compress(body, content_encoding):
        '''Compress the provided content subject to the content encoding'''
        if content_encoding == 'gzip':
            import gzip
            from cStringIO import StringIO
            ios = StringIO()
            fout = gzip.GzipFile(fileobj=ios, mode='wb')
            fout.write(body)
            fout.close()
            return ios.getvalue()
        elif content_encoding == 'deflate':  # pragma: no branch
            # This is a piece of code I find a little contentious. Apparently,
            # some browsers interpret `deflate` as a full zlib stream (with
            # header and checksum, and others interpret it merely as the
            # deflate stream. Chrome interprets both, and I've not tested
            # others. Reportedly Microsoft interprets it strictly as deflate:
            #
            #       http://www.zlib.net/zlib_faq.html#faq39
            #
            # The `requests` module only automatically decompresses it if it's
            # in the stream-only (and no header, checksum) format, and so
            # that's we implement here, following the conclusion of a stack
            # overflow discussion:
            #
            # http://stackoverflow.com/questions/1089662/python-inflate-and-deflate-implementations
            import zlib
            return zlib.compress(body)[2:-4]

    def __init__(self, path):
        self.path = path

    def read(self, path):
        '''Reads the contenst of a file, manipulates the headers and responds
        with the content to send back'''
        # Open the provided file, and read it
        logger.debug('Opening %s...' % os.path.join(self.path, path))
        with open(os.path.join(self.path, path)) as fin:
            logger.debug('    Reading...')
            lines = fin.read().split('\n')
            # First, the status line
            logger.debug('    Reading status line...')
            if lines[0].startswith('HTTP'):
                response.status = lines[0].partition(' ')[2]
            else:
                response.status = lines[0]

            # Find the empty line, which corresponds to the end of our headers
            logger.debug('    Finding end of headers...')
            try:
                index = lines.index('')
            except ValueError:
                index = len(lines)

            # Now take those lines and interpret them as headers
            logger.debug('    Reading headers...')
            response.headers.pop('Content-Type', None)
            for line in lines[1:index]:
                key, sep, value = line.partition(': ')
                # Headers are supposed to be iso-8859-1
                response.headers[key] = value

            # If there were only headers, then return empty content
            if index == len(lines):
                return ''

            # Listen for any directives for Asis
            directives = [d.strip().lower()
                for d in str(response.headers.pop('Asis', '')).split(';')]

            # Unless there's a directive to not encode headers, then encode 
            if 'no-header-encode' not in directives:
                for key, value in response.headers.items():
                    response.headers[key] = value.decode(
                        'utf-8').encode('iso-8859-1')

            # Otherwise, content is the remainder of the document
            content = '\n'.join(lines[(index + 1):])
            # If there are any transformation we have to apply, then apply them
            # First, check if there's a character set specified
            charset = response.headers.get(
                'Content-Type', '').partition('; charset=')[2]
            if charset and ('no-charset' not in directives):
                logger.debug('Encoding to character set: %s' % charset)
                content = content.decode('utf-8').encode(charset)
                # Update the Content-Length if one was included
                if response.headers.get('Content-Length'):
                    response.headers['Content-Length'] = len(content)

            # Now, check to see if any content encoding has been specified
            encoding = response.headers.get('Content-Encoding', '')
            if encoding and encoding in self.supported_encodings and (
                'no-encoding' not in directives):
                logger.debug('Encoding to %s' % encoding)
                # Encode it, and update Content-Length
                content = self.compress(content, encoding)
                if response.headers.get('Content-Length'):
                    logger.debug('New Content-Length %s' % len(content))
                    response.headers['Content-Length'] = len(content)
            elif encoding:
                logger.warn('Encoding %s not supported' % encoding)

            logger.debug('    Headers: %s' % dict(response.headers))
            logger.debug('    Returning content...')
            return content

    def handle(self, path):
        '''Handle a given request'''
        # There's only one header that gets pre-loaded, and so we'll delete it
        try:
            return self.read(path)
        except IOError:
            abort(404, 'File Not Found')
        except:
            logger.exception('Unexpected error')
            import traceback
            abort(500, traceback.format_exc())


class Server(object):
    '''Server holding the bottle app and tooling to run it in different modes.'''

    def __init__(self, path, host='0.0.0.0', port=80, server='cherrypy'):
        self.host = host
        self.port = port
        self.server = server
        self.app = Bottle()
        self.app.route('/<path:path>')(Handler(path).handle)

    def run(self):
        '''Start running the server'''
        run(self.app, host=self.host, port=self.port, server=self.server)

    def check_ready(self, timeout=0.01):
        '''Wait until host is accepting connections on the provided port.'''
        timeout = 0.01
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        if sock.connect_ex((self.host, self.port)) == 0:
            return True
        return False

    @contextlib.contextmanager
    def fork(self):
        '''Run an asis server in a separate process.'''
        logger.info('Forking server with %s', self.server)
        pid = os.fork()
        if pid == 0:  # pragma: no cover
            # I'm the child process
            try:
                self.run()
            finally:
                os._exit(0)
        else:
            # Wait for the child process to be ready and responding
            while True:
                try:
                    os.kill(pid, 0)
                except OSError:
                    raise RuntimeError('Child process died.')
                else:
                    if self.check_ready():
                        logger.info('Server started in %s', pid)
                        break

            try:
                yield
            finally:
                # SIGINT and wait for the child to finish
                os.kill(pid, 2)
                os.waitpid(pid, 0)

    @contextlib.contextmanager
    def greenlet(self):
        '''Run an asis server in a greenlet.'''
        # Ensure that monkey-patching has happened before running the server.
        # We avoid aggressively monkey-patching at the top of the file since
        # this class may be used from many contexts, including potentially
        # without the advent of `gevent`.
        from gevent import monkey
        monkey.patch_all()

        import gevent
        spawned = gevent.Greenlet.spawn(self.run)
        try:
            # Wait until something is listening on the specified port. Two
            # outcomes are possible -- an exception happens and the greenlet
            # terminates, or it starts the server and is listening on the
            # provided port.
            while spawned:
                if self.check_ready():
                    break

            # If the greenlet had an exception, re-raise it in this context
            if not spawned:
                raise spawned.exception

            yield spawned
        finally:
            spawned.kill(KeyboardInterrupt, block=True)
            spawned.join()
