"""Optional, source-bound presentation edits; original generated results stay intact."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

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


APPROVAL_KEYS = ('job_id', 'revision', 'proposal_sha256', 'moment_ids', 'style', 'lighting')


def inherited_manifest(previous_result, previous_manifest, previous_approval, result, approval, previous_id):
    """Carry a curated layout only to a repeat of the same approved source moments."""
    if any(previous_approval.get(key) != approval.get(key) for key in APPROVAL_KEYS):
        return None
    if previous_manifest.get('version') != 1:
        return None
    old = {asset['id']: asset for asset in previous_result['assets']}
    new = {asset['id']: asset for asset in result['assets']}
    if (not old or old.keys() != new.keys()
            or any(old[key]['source_sha256'] != new[key]['source_sha256'] for key in old)):
        return None
    items = previous_manifest.get('assets', [])
    if not items or len({item.get('id') for item in items}) != len(items):
        return None
    for item in items:
        prior = old.get(item.get('id'))
        if (not prior or item.get('source_sha256') != prior['source_sha256']
                or item.get('mesh_sha256') != prior['mesh_sha256']
                or item.get('preset') not in PRESETS):
            return None
    return {
        'version': 1,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'request': 'Reuse the earlier curated presentation for the same approved source moments.',
        'method': 'Curated scene assembly; original generated meshes and timings retained.',
        'reused_from_generation': previous_id,
        'assets': [{'id': item['id'], 'source_sha256': new[item['id']]['source_sha256'],
                    'mesh_sha256': new[item['id']]['mesh_sha256'], 'preset': item['preset']}
                   for item in items],
    }


def carry_forward_presentation(store, generation, result):
    """Copy the latest matching presentation after generation, without touching output meshes."""
    with store.db() as db:
        current = db.execute('SELECT project,job,approval FROM generations WHERE id=?', (generation,)).fetchone()
        previous = db.execute(
            "SELECT id,approval FROM generations WHERE project=? AND job=? AND status='ready' "
            "AND id<>? ORDER BY created DESC", (current['project'], current['job'], generation)).fetchall()
    directory = store.generation_dir(current['project'], generation)
    destination = directory / 'presentation.json'
    if destination.exists():
        return False
    approval = json.loads(current['approval'])
    for row in previous:
        prior_dir = store.generation_dir(current['project'], row['id'])
        if not (prior_dir / 'presentation.json').is_file():
            continue
        try:
            old_result = json.loads((prior_dir / 'result.json').read_text())
            old_manifest = json.loads((prior_dir / 'presentation.json').read_text())
            manifest = inherited_manifest(old_result, old_manifest, json.loads(row['approval']),
                                          result, approval, row['id'])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if manifest is None:
            continue
        fd, temporary = tempfile.mkstemp(prefix='presentation-', suffix='.json', dir=directory)
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(manifest, handle, indent=2)
                handle.write('\n')
            attach_presentation(json.loads(json.dumps(result)), Path(temporary))
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True
    return False
