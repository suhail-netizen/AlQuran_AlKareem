#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serves the Quran reader app locally and opens it in the browser:

    python viewer/serve.py            (port 8000)
    python viewer/serve.py 8080

Run viewer/build_pages.py once first to create the page files. Browsers block fetch() on file://,
so opening index.html directly will not load the pages.
"""

import functools
import http.server
import os
import sys
import threading
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    # Revalidate every time (cheap 304s) so regenerated pages and app edits show up on reload.
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    ports = [a for a in sys.argv[1:] if a.isdigit()]
    port = int(ports[0]) if ports else 8000
    Handler.extensions_map = {**Handler.extensions_map,
                              '.js': 'text/javascript', '.html': 'text/html; charset=utf-8',
                              '.webmanifest': 'application/manifest+json'}
    handler = functools.partial(Handler, directory=ROOT)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    if not os.path.isdir(os.path.join(ROOT, 'Pages')):
        print('No page files yet: run  python viewer/build_pages.py  first.')
    url = f'http://127.0.0.1:{port}/index.html'
    print(f'Quran reader: {url}  (Ctrl+C to stop)')
    if '--no-browser' not in sys.argv:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
