"""Package actual pipeline outputs in an interactive, inspectable keepsake."""
import argparse
import base64
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    run = args.run
    data = {
        'world': json.loads((run / 'analysis/world_spec.json').read_text()),
        'observations': json.loads((run / 'analysis/journey_observations.json').read_text()),
        'source': json.loads((run / 'input/source.json').read_text()),
        'build': json.loads((run / 'output/build_report.json').read_text()),
    }
    ending = run / 'analysis/ending_check.json'
    if ending.exists():
        data['ending_check'] = json.loads(ending.read_text())
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', data['source']['video_id']):
        raise ValueError('Invalid source video ID')
    glb = base64.b64encode((run / 'output/my-travel-journey.glb').read_bytes()).decode()
    template = Path(__file__).with_name('viewer.html').read_text()
    # Model responses are data, never HTML or executable JavaScript.
    encoded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = template.replace('__JOURNEY_DATA__', encoded).replace('__JOURNEY_GLB__', glb)
    (run / 'output/viewer.html').write_text(template)
    print('VIEWER_CREATED', run / 'output/viewer.html')


if __name__ == '__main__':
    main()
