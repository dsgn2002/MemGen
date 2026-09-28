#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess

from trip_upload.config import ROOT, Settings
from trip_upload.store import Store, now


def main():
    parser = argparse.ArgumentParser(description='Private upload-to-evidence service')
    sub = parser.add_subparsers(dest='command', required=True)
    invite = sub.add_parser('invite')
    invite.add_argument('--name', required=True)
    invite.add_argument('--days', type=int, default=30)
    serve = sub.add_parser('serve')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8890)
    worker = sub.add_parser('worker')
    worker.add_argument('--once', action='store_true')
    sub.add_parser('cleanup')
    sub.add_parser('preflight')
    args = parser.parse_args()
    settings = Settings.env()
    if args.command == 'invite':
        if not 1 <= args.days <= 90:
            parser.error('Invitation duration must be 1..90 days.')
        print(Store(settings.data).invite(args.name, args.days))
    elif args.command == 'serve':
        import uvicorn
        from trip_upload.app import create_app
        uvicorn.run(create_app(settings), host=args.host, port=args.port, proxy_headers=False, access_log=False)
    elif args.command == 'worker':
        from trip_upload.worker import work
        work(settings, args.once)
    elif args.command == 'preflight':
        from trip_upload.media import Image
        # The API venv intentionally has no Torch. Check the configured GPU
        # interpreter rather than incorrectly rejecting a healthy deployment.
        try:
            checked = subprocess.run([settings.worker_python, str(ROOT.parent / 'skills/tools.py'),
                                      'preflight', '--model-path', settings.model],
                                     capture_output=True, text=True, timeout=60)
            report = json.loads(checked.stdout)
            report['ok'] = report['ok'] and checked.returncode == 0
            if checked.returncode:
                report['worker_error'] = checked.stderr[-2000:]
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            report = {'ok': False, 'worker_error': str(e)}
        report['worker_python'] = settings.worker_python
        report['photo_decoder_heif'] = 'HEIF' in Image.OPEN
        report['ok'] = report['ok'] and report['photo_decoder_heif']
        print(json.dumps(report, indent=2))
        return 0 if report['ok'] else 1
    else:
        store = Store(settings.data)
        print(f'Removed {store.cleanup()} expired projects.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
