"""Download a public model on the compute host in resumable, verified chunks."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bytes', type=int, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and hashlib.sha256(args.output.read_bytes()).hexdigest() == args.sha256:
        print('MODEL_ALREADY_VERIFIED', flush=True)
        return
    parts = args.output.with_suffix('.parts')
    parts.mkdir(exist_ok=True)
    chunk = 2 * 1024 * 1024
    count = (args.bytes + chunk - 1) // chunk

    def get(index):
        start = index * chunk
        end = min(args.bytes, start + chunk) - 1
        target = parts / f'{index:04d}'
        if target.exists() and target.stat().st_size == end - start + 1:
            return index
        for attempt in range(4):
            try:
                request = urllib.request.Request(args.url, headers={
                    'Range': f'bytes={start}-{end}', 'User-Agent': 'MyTravelJourney/1.0',
                    'Accept-Encoding': 'identity'})
                with urllib.request.urlopen(request, timeout=120) as response:
                    expected = f'bytes {start}-{end}/{args.bytes}'
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('Server did not honor the requested byte range')
                    data = response.read(end - start + 2)
                if len(data) != end - start + 1:
                    raise ValueError('Incomplete download chunk')
                temporary = target.with_suffix('.part')
                temporary.write_bytes(data)
                temporary.replace(target)
                return index
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 + attempt * 3)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for completed, future in enumerate(as_completed([executor.submit(get, i) for i in range(count)]), 1):
            future.result()
            print(f'DOWNLOAD {completed}/{count} chunks', flush=True)
    temporary = args.output.with_suffix('.assembling')
    digest = hashlib.sha256()
    with temporary.open('wb') as output:
        for i in range(count):
            data = (parts / f'{i:04d}').read_bytes()
            digest.update(data)
            output.write(data)
    if digest.hexdigest() != args.sha256:
        raise ValueError('Model checksum mismatch; refusing to load it')
    temporary.replace(args.output)
    print(f'MODEL_VERIFIED {args.sha256}', flush=True)


if __name__ == '__main__':
    main()
