"""Explicit operator test through the real HTTP API and deployed local-Qwen worker.

Run on the same host as the private data directory. Creates a dedicated test
invitation; never prints its credential. No fake inference or supplied timestamps.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from trip_upload.config import Settings
from trip_upload.store import Store
from memgen_skills.evidence import validate_brief


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--photos',nargs='+',type=Path)
    p.add_argument('--video',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    saved=json.loads(args.out.read_text()) if args.check else {'code':Store(Settings.env().data).invite('Live pipeline verification'), 'projects':[]}
    with httpx.Client(base_url='http://127.0.0.1:8890',timeout=120) as client:
        r=client.post('/api/login',json={'code':saved['code']});r.raise_for_status()
        # Explicit loopback test; production browsers use the Secure cookie over HTTPS.
        client.headers.update({'Cookie':'trip_session='+r.cookies['trip_session'],'X-CSRF-Token':r.json()['csrf']})
        if args.check:
            for item in saved['projects']:
                r=client.get('/api/projects/'+item['id']);r.raise_for_status()
                project=r.json();item['status']=project['status'];item['stage']=project['job']['stage'];item['error']=project['job']['error']
                if project['status'] in {'review','approved'}:
                    r=client.get(f"/api/projects/{item['id']}/proposal");r.raise_for_status();proposal=r.json()
                    assert proposal['proposal']['provenance']['model']['provider']=='local_qwen'
                    # Both smoke requests explicitly ask for a natural rendering look.
                    assert any(r['kind']=='creative_change' and 'natural' in r['description'].lower()
                               and not r['needs_visual_evidence'] for r in proposal['proposal']['intent']['requirements'])
                    item['style_intent_check']='passed'
                    item['moments']=len(proposal['proposal']['moments'])
                    item['requirements']=proposal['proposal']['requirements']
                    item['model_calls']=proposal['proposal']['provenance']['model']['calls']
                    item['model']=proposal['proposal']['provenance']['model']
                    item['source_hashes']=proposal['proposal']['provenance']['source_hashes']
                    item['queue_to_proposal_seconds']=round(project['job']['updated']-project['job']['created'],2)
                    run=Store(Settings.env().data).job_dir(item['id'],item['job_id'])
                    item['structured_correction_attempts']=len(list(run.rglob('attempt-2.response.txt')))
                    for m in proposal['proposal']['moments']:
                        r=client.get(f"/api/projects/{item['id']}/artifacts/{m['image']}");r.raise_for_status()
                        for ref in m['references']:
                            r=client.get(f"/api/projects/{item['id']}/artifacts/{ref['image']}");r.raise_for_status()
                            assert hashlib.sha256(r.content).hexdigest()==ref['sha256']
                        if m.get('clip'):
                            r=client.get(f"/api/projects/{item['id']}/artifacts/{m['clip']}",headers={'Range':'bytes=0-31'})
                            assert r.status_code==206 and len(r.content)==32
                    item['artifact_checks']='passed'
                    if item['kind']=='video':
                        folder=run/'evidence'
                        brief=json.loads((folder/'evidence-brief.json').read_text())
                        validate_brief(brief,folder)
                        item['sampling']={k:brief['sampling'][k] for k in ['coarse_budget','refinement_budget','coarse_frames','refinement_frames']}
                        item['video_contract_check']='passed'
                    if item['moments']:
                        body={'job_id':item['job_id'],'revision':item['revision'],'proposal_sha256':proposal['sha256'],
                              'moment_ids':[m['id'] for m in proposal['proposal']['moments']],
                              'style':'natural','lighting':'day','notes':'Operator smoke-test approval; not a user-selected generation job.'}
                        r=client.post(f"/api/projects/{item['id']}/approve",json=body);r.raise_for_status()
                        assert not r.json()['approval']['generation_started']
                        item['approval_check']='passed'
                        item['status']='approved'
        else:
            cases=[]
            if args.photos:cases.append(('photos',args.photos,'Highlight the city buildings and street scene. Keep a natural, realistic look.'))
            if args.video:cases.append(('video',[args.video],'Highlight the visible people in the outdoor scene. Keep a natural look.'))
            for kind,files,request in cases:
                r=client.post('/api/projects',json={'title':'Live verification · '+kind,'request':request});r.raise_for_status();pid=r.json()['id']
                for file in files:
                    r=client.post(f'/api/projects/{pid}/uploads',json={'name':file.name,'kind':'photo' if kind=='photos' else 'video','size':file.stat().st_size});r.raise_for_status();upload=r.json()
                    offset=0
                    with file.open('rb') as f:
                        for chunk in iter(lambda:f.read(upload['chunk_size']),b''):
                            r=client.put(f"/api/projects/{pid}/uploads/{upload['id']}?offset={offset}",content=chunk);r.raise_for_status();offset=r.json()['offset']
                    r=client.post(f"/api/projects/{pid}/uploads/{upload['id']}/complete");r.raise_for_status()
                r=client.post(f'/api/projects/{pid}/analyze',json={'request':request});r.raise_for_status()
                saved['projects'].append({'kind':kind,'id':pid,**r.json()})
        args.out.write_text(json.dumps(saved,indent=2));args.out.chmod(0o600)
        print(json.dumps(saved['projects'],indent=2))


if __name__=='__main__':main()
