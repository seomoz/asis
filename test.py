# -*- coding: utf-8 -*-
#
#! /usr/bin/env python
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

'''Our unit test, y'all'''

from gevent import monkey
monkey.patch_all()

import asis
import mock
import logging
import unittest
import requests

asis.logger.setLevel(logging.WARNING)


class AsisTest(unittest.TestCase):
    '''Yep, it's all of our tests'''

    base = 'http://localhost:8080/'

    @classmethod
    def setUpClass(cls):
        cls.server = asis.Server('test', port=8080, server='gevent')
        cls.context = cls.server.greenlet()
        cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_basic(self):
        '''Works in the most basic way'''
        content = requests.get(self.base + 'basic/basic.asis').content
        self.assertIn(b'test page', content)

    def test_redirect(self):
        '''Can follow redirects'''
        req = requests.get(self.base + 'basic/301.asis')
        self.assertEqual(len(req.history), 1)
        self.assertIn(b'test page', req.content)

    def test_404(self):
        '''If there is no document there, it responds with a 404'''
        req = requests.get(self.base + 'basis/alksjdlfwoieuroaksjd;lfkjas')
        self.assertEqual(req.status_code, 404)

    def test_empty(self):
        '''An empty document should fail gracefully'''
        req = requests.get(self.base + 'basic/empty.asis')
        self.assertEqual(req.status_code, 500)
        self.assertNotEqual(len(req.content), 0)

    def test_headers_only(self):
        '''When there's only header content, we should succeed well'''
        req = requests.get(self.base + 'basic/only-headers.asis')
        self.assertEqual(len(req.content), 0)

    def test_compression(self):
        '''Gzip, deflate and zlib should work correctly.'''
        req = requests.get(self.base + 'encoding/gzip.asis')
        # Because the requests library automatically decompresses encoded
        # files, we'll make sure that its content-length and the content's
        # length don't match. And it should mention that it's gzip-compressed
        self.assertNotEqual(req.headers['content-length'], len(req.content))
        self.assertIn(b'Gzip', req.content)

        # Same for deflate
        req = requests.get(self.base + 'encoding/deflate.asis')
        self.assertNotEqual(req.headers['content-length'], len(req.content))
        self.assertIn(b'Deflate', req.content)

        # But for unsupported compression schemes, it shouldn't change anything
        # It should still work, though.
        req = requests.get(self.base + 'encoding/unsupported.asis')
        self.assertIn(b'Unsupported', req.content)

    def test_encoding(self):
        '''It should update the encodings provided correctly'''
        iso_encodings = [('iso-8859-%i' % num) for num in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 16]]
        windows_encodings = [('windows-%i' % num) for num in range(1250, 1259)]

        encodings = iso_encodings + windows_encodings
        for encoding in encodings:
            encoding_bytes = bytes(encoding, encoding=encoding)
            path = 'encoding/%s.asis' % encoding
            req = requests.get(self.base + path)
            # Each of the encoded files has the name of its encoding in it
            self.assertTrue(encoding_bytes in req.content)
            # Also, none of these should parse when interpreted as UTF-8
            self.assertRaises(Exception, bytes.decode, req.content, 'utf-8')

    def test_charset_no_length(self):
        '''When a charset is used, but a content-length is absent, none is provided.'''
        # Just exercise this branch
        requests.get(self.base + 'basic/charset-no-length.asis')

    def test_encoding_no_length(self):
        '''When an encoding is used, but a content-length is absent, none is provided.'''
        # Just exercise this branch
        requests.get(self.base + 'basic/encoding-no-length.asis')

    def test_check_ready_true(self):
        '''Returns true if the server is ready.'''
        self.assertTrue(self.server.check_ready())

    def test_check_ready_false(self):
        '''Returns false if the server is not ready.'''
        self.assertFalse(asis.Server('test', port=8081).check_ready())

    def test_raises_spawned_exception(self):
        '''Reraises spawned greenlet exceptions.'''
        server = asis.Server('test', port=8081, server='gevent')
        with mock.patch.object(server, 'run', side_effect=ValueError('kaboom')):
            with self.assertRaises(ValueError):
                with server.greenlet():
                    pass

    def test_fork_basic(self):
        '''Forking server works.'''
        server = asis.Server('test', port=8081, server='gevent')
        with server.fork():
            req = requests.get('http://localhost:8081/basic/basic.asis')
            self.assertEqual(req.status_code, 200)

    def test_fork_early_exit(self):
        '''Raises an exception if the child process exits early.'''
        server = asis.Server('test', port=8081, server='gevent')
        with mock.patch.object(server, 'run', side_effect=ValueError('kaboom')):
            with self.assertRaises(RuntimeError):
                with server.fork():
                    pass
