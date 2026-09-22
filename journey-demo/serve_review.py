"""Serve the Stage 1 review on localhost and save an explicit scene handoff.

No model or generation job is launched here. The saved brief is the input for
the next stage; a recommendation or radio change is never a confirmed choice.
"""
import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit


class ReviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, run, **kwargs):
        self.run = run
        super().__init__(*args, directory=str(run / 'output'), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def json_response(self, status, data, download=False):
        encoded = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        if download:
            self.send_header('Content-Disposition', 'attachment; filename="selected-scene-brief.json"')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def saved_selection(self):
        path = self.run / 'selection.json'
        return json.loads(path.read_text()) if path.exists() else None

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in {'/api/selection', '/api/selection/download'}:
            selection = self.saved_selection()
            if path.endswith('/download'):
                self.json_response(200 if selection else 404,
                    selection or {'error': 'Choose and save a scene first.'}, download=bool(selection))
            else:
                self.json_response(200, {'selection': selection})
        elif path.startswith('/api/'):
            self.json_response(404, {'error': 'Unknown endpoint.'})
        else:
            super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != '/api/selection':
            return self.json_response(404, {'error': 'Unknown endpoint.'})
        expected_host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected_host or self.headers.get('Origin') != 'http://' + expected_host:
            return self.json_response(403, {'error': 'Save selections from the local journey review page.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.json_response(415, {'error': 'Expected a JSON selection.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Selection request is too large or empty.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or set(data) != {'scene_ids', 'user_notes', 'review_version'}:
                raise ValueError('Expected selected scenes, review version, and optional notes.')
            notes = data['user_notes']
            if not isinstance(notes, str) or len(notes) > 2000:
                raise ValueError('Notes must be at most 2,000 characters.')
            review = json.loads((self.run / 'output/review.json').read_text())
            if data['review_version'] != review['review_version']:
                return self.json_response(409, {'error': 'This review has changed. Reload it before choosing a scene.'})
            ids = data['scene_ids']
            if not isinstance(ids, list) or not 1 <= len(ids) <= len(review['scenes']) or any(not isinstance(x, str) for x in ids):
                raise ValueError('Choose at least one of the suggested scenes.')
            scenes = [item for item in review['scenes'] if item['id'] in ids]
            if len(scenes) != len(ids):
                raise ValueError('Selected scenes must be unique and from this review.')
            selection = {
                'schema_version': 2, 'status': 'selected_for_generation',
                'selected_at': datetime.now(timezone.utc).isoformat(),
                'review_version': review['review_version'], 'source': review['source'],
                'scenes': scenes, 'user_notes': notes.strip(),
                'generation_requirements': review['generation_requirements'],
                'generation_started': False,
            }
            # Copy scene evidence from the authoritative review, never client JSON.
            # Atomic replacement also allows another process to read a complete brief.
            with self.server.selection_lock:
                temporary = self.run / 'selection.json.tmp'
                temporary.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + '\n')
                temporary.replace(self.run / 'selection.json')
            self.json_response(200, {'selection': selection})
        except (ValueError, UnicodeDecodeError) as error:
            self.json_response(400, {'error': str(error)})
        except OSError:
            self.json_response(500, {'error': 'Could not save the scene. Check that the review folder is writable.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    run = args.run.resolve()
    if not (run / 'output/review.json').is_file():
        parser.error('Render the journey review before starting the server.')
    handler = partial(ReviewHandler, run=run)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    server.selection_lock = threading.Lock()
    print(f'My Travel Journey review: http://127.0.0.1:{args.port}/', flush=True)
    print(f'Confirmed choices are saved to {run / "selection.json"}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
