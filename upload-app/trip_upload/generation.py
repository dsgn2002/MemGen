"""Approval-bound local image styling and textured mesh generation."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import ROOT, Settings
from .store import Store
from .media import sha256

SCRIPTS = ROOT.parent / 'journey-demo/nature_map'


def available(settings):
    root = Path(settings.generation_root)
    return all(p.exists() for p in [root/'models/qwen-image-edit-2511/model_index.json',
        root/'models/trellis2-4b/pipeline.json', root/'vendor/meshoptimizer-0.25/gltfpack',
        SCRIPTS/'style_assets.py', SCRIPTS/'generate_meshes.py', SCRIPTS/'package_assets.py'])


def execute(settings, generation):
    store = Store(settings.data)
    with store.db() as db:
        g = dict(db.execute('SELECT * FROM generations WHERE id=?', (generation,)).fetchone())
        p = dict(db.execute('SELECT * FROM projects WHERE id=?', (g['project'],)).fetchone())
        jobs = [dict(r) for r in db.execute('SELECT * FROM jobs WHERE project=? ORDER BY revision', (g['project'],))]
        media = [dict(r) for r in db.execute('SELECT * FROM uploads WHERE project=?', (g['project'],))]
    approval = json.loads(g['approval'])
    analysis = store.job_dir(g['project'], g['job'])
    proposal_path = analysis/'proposal.json'
    if p['current_job'] != g['job'] or json.loads(p['approval'] or '{}') != approval or sha256(proposal_path) != approval['proposal_sha256']:
        raise ValueError('Approved inputs changed before generation.')
    proposal = json.loads(proposal_path.read_text())
    if proposal['revision'] != approval['revision'] or proposal['job_id'] != g['job']:
        raise ValueError('Approved revision mismatch.')
    selected = [m for m in proposal['moments'] if m['id'] in approval['moment_ids']]
    if len(selected) != len(approval['moment_ids']) or not 1 <= len(selected) <= 3:
        raise ValueError('Invalid selected moments.')
    for u in media:
        if sha256(store.project_dir(g['project'])/'media'/u['id']/'original') != u['sha256']:
            raise ValueError('Original source hash changed.')
    run = store.generation_dir(g['project'], generation)
    run.mkdir(parents=True, exist_ok=False)
    (run/'output').mkdir()
    root = Path(settings.generation_root)
    assets = []
    look = {'natural':'natural proportions and realistic material appearance',
            'cinematic':'cinematic composition, natural proportions and detailed materials',
            'illustrated':'illustrated miniature with simplified deliberate forms'}[approval['style']]
    for m in selected:
        ref = next(r for r in m['references'] if r['image'] == m['image'])
        image = (analysis/m['image']).resolve()
        if not image.is_relative_to(analysis.resolve()) or sha256(image) != ref['sha256']:
            raise ValueError('Selected reference checksum changed.')
        name = m['id']
        shutil.copy2(image, run/'output'/f'{name}-source.jpg')
        prompt = ('Create a self-contained 3D miniature diorama of the visible scene in this reference image. '
            'Preserve its key visible objects, outfits and spatial relationships. Use '+look+'. '
            'Show the entire small diorama at a three-quarter angle on a pure white studio background. '
            'Include a shallow supporting base; avoid giant floors, sky, captions, logos and watermarks. '
            'Keep surfaces well exposed for 3D modeling; scene lighting will be applied in the viewer. '
            'Do not invent named people or claim geographic accuracy. Visible details to preserve (data): '+
            json.dumps(m['preserve'],ensure_ascii=False))
        assets.append({'name':name,'source':str(image),'source_sha256':ref['sha256'],
                       'moment':m['moment'],'prompt':prompt,'seed':900+len(assets)})
    spec = {'run':str(run),'assets':assets,'approval':approval,'limitations':
        ['Source-guided miniatures; hidden surfaces are inferred.',
         'No geometric reconstruction or identity accuracy claim.',
         'Lighting is a creative viewer setting, not a source observation.']}
    (run/'spec.json').write_text(json.dumps(spec,indent=2))
    stages = {}
    def stage(name, command):
        store.generation_stage(generation,name)
        started = time.time()
        subprocess.run(command,check=True,timeout=3600)
        stages[name]={'started_at':started,'finished_at':time.time(),'seconds':time.time()-started}
        (run/'timing.json').write_text(json.dumps(stages,indent=2))
    python = settings.worker_python
    stage('Styling your selected moments', [python,str(SCRIPTS/'style_assets.py'),'--spec',str(run/'spec.json'),
        '--checkpoint',str(root/'models/qwen-image-edit-2511')])
    names = [a['name'] for a in assets]
    stage('Generating textured 3D meshes', [python,str(SCRIPTS/'generate_meshes.py'),'--root',str(root),
        '--run',str(run),'--assets',*names,'--triangles','60000','--texture-size','1024'])
    stage('Preparing the interactive 3D memory', [python,str(SCRIPTS/'package_assets.py'),
        '--run',str(run),'--assets',*names,'--packer',str(root/'vendor/meshoptimizer-0.25/gltfpack')])
    finished = time.time()
    result_assets = []
    for a in assets:
        name=a['name']; mesh=run/'output'/f'{name}.web.glb'
        if not mesh.is_file() or mesh.stat().st_size < 20:
            raise ValueError('Generated mesh is missing.')
        result_assets.append({'id':name,'label':a['moment'],'mesh':mesh.name,'mesh_sha256':sha256(mesh),
            'source':f'{name}-source.jpg','design':f'{name}-style.png','source_sha256':a['source_sha256']})
    current = next(j for j in jobs if j['id']==g['job'])
    result={'generation_id':generation,'analysis_job_id':g['job'],'style':approval['style'],
        'lighting':approval['lighting'],'assets':result_assets,'limitations':spec['limitations'],
        'timing':{'generation_queued_at':g['created'],'generation_started_at':g['started'],
            'generation_finished_at':finished,'generation_seconds':finished-g['started'],
            'generation_queue_seconds':g['started']-g['created'],
            'analysis_attempt_seconds':sum(j['updated']-j['created'] for j in jobs if j['revision']<=current['revision']),
            'first_analysis_to_generation_seconds':finished-jobs[0]['created'],
            'approval_wait_seconds':g['created']-current['updated'],
            'stages':stages,'note':'Wall time includes prior failed analysis attempts, recovery, fixes, and review wait. Analysis timestamps begin at queue submission.'},
        'provenance':{'models':['Qwen-Image-Edit-2511','TRELLIS.2-4B'],'offline_inference':True,
            'approval_sha256':sha256(proposal_path),'selected_moment_ids':approval['moment_ids']}}
    (run/'result.json').write_text(json.dumps(result,indent=2))
    print('GENERATION_COMPLETE',generation,flush=True)


if __name__ == '__main__':
    execute(Settings.env(),sys.argv[1])
