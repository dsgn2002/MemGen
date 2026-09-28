"""Optional, source-bound presentation edits; original generated results stay intact."""
import json

PRESETS = {'dining-characters-v1', 'lantern-display-v1'}


def attach_presentation(result, path):
    if not path.exists():
        return result
    manifest = json.loads(path.read_text())
    if manifest.get('version') != 1:
        raise ValueError('Unsupported presentation version.')
    known = {a['id']: a for a in result['assets']}
    for item in manifest.get('assets', []):
        asset = known.get(item.get('id'))
        if (not asset or item.get('source_sha256') != asset['source_sha256']
                or item.get('mesh_sha256') != asset['mesh_sha256']
                or item.get('preset') not in PRESETS):
            raise ValueError('Presentation does not match its source and generated mesh.')
        asset['presentation'] = {'preset': item['preset'], 'version': 1,
            'method': 'Curated scene assembly with generic assets; no identity reconstruction.'}
    return result
