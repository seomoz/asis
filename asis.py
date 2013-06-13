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

import os
import re
import logging
from bottle import Bottle, run, response, abort


# Our logger
logger = logging.getLogger('asis')
formatter = logging.Formatter('[%(asctime)s] %(levelname)s : %(message)s')
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.WARNING)


class Server(object):
    '''Regular expression for matching found headers'''
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
        elif content_encoding == 'deflate':
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

    def __init__(self, path, port=80, server='gevent', mode='gevent'):
        '''Mode should be one of:
            - gevent   (runs in separate green thread)
            - fork     (forks off sub process)
            - block    (blocks the process)
        '''
        self.app = Bottle()
        self.pid = None
        self.mode = mode
        self.path = path
        self.port = port
        self.server = server

    def __enter__(self):
        self.run()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

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

    def _run(self):
        '''Actually run the server, whether it's in a separate process, or
        blocking or in a green thread'''
        try:
            run(self.app, host='', port=self.port, server=self.server)
        except KeyboardInterrupt:
            # Finished
            pass

    def run(self):
        '''Start running the server'''
        self.app.route('/<path:path>')(self.handle)
        if self.mode == 'fork':
            logger.info('Forking server with %s' % self.server)
            self.pid = os.fork()
            if self.pid == 0:
                # I'm the child process
                self._run()
                exit(0)
            else:
                import time
                time.sleep(1)
                logger.info('Server started in %s' % self.pid)
        elif self.mode == 'gevent':
            logger.info('Launching server in greenlet %s' % self.server)
            from gevent import Greenlet
            self.pid = Greenlet.spawn(self._run)
            # We actually need to wait a very short time before saying that
            # it's started. I believe that all this does is to yield control
            # from this green thread to the other green thread briefly
            self.pid.join(0.01)
        else:
            # Blocking
            self._run()

    def stop(self):
        '''Stop running the server'''
        logger.info('Shutting down server...')
        if self.mode == 'fork':
            # Send SIGINT
            os.kill(self.pid, 2)
            # And then wait for the process to terminate
            os.waitpid(self.pid, 0)
            self.pid = None
        elif self.mode == 'gevent':
            # Raise the KeyboardInterrupt in the green thread, and wait for it
            logger.debug('Killing greenlet')
            import gevent
            self.pid.kill(gevent.GreenletExit, block=True)
            self.pid = None
        else:
            self.app.close()
