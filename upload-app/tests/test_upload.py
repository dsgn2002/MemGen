"""Real HTTP/media tests; local model responses below are explicit test doubles."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from PIL import Image
from trip_upload.app import create_app
from trip_upload.config import Settings
from trip_upload.store import Store
from trip_upload.pipeline import execute
from trip_upload.media import sha256


class FixtureModel:
    """Deterministic fixture, never available through the HTTP API or worker."""
    def metadata(self):
        return {'provider':'explicit_test_double', 'offline':True}

    def generate(self, prompt, images, max_tokens):
        if 'Recommend up to three' in prompt:
            return json.dumps({'recommendations':[{'style':'natural','lighting':'day','reason':'Explicit test fixture.'}]})
        if '\nPAIRS: ' in prompt:
            pairs=json.loads(prompt.split('\nPAIRS: ')[1].split('\nReturn ONLY')[0])
            return json.dumps({'views':[[i,1,'A test person','Test outdoor setting','group',['Test shirt']] for i in range(len(images))],
                               'checks':[[i,j,'visible','Explicit fixture'] for i,j in pairs]})
        if 'FRAME ORDER:' in prompt:
            return json.dumps({'frames':[[i,1,'group',[0],[],'A test person','Test outdoor setting',['Test shirt']] for i in range(len(images))]})
        return json.dumps({'requirements':[{'kind':'subject','description':'Visible person','priority':3,
            'source_quote':'Highlight the visible person.'}], 'ambiguities':[], 'moment_count':3})


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.settings=Settings(Path(self.tmp.name), model='/explicit/test/checkpoint', secure_cookie=False, coarse=3, refinement=0)
        self.app=create_app(self.settings)
        self.store=self.app.state.store
        self.client=TestClient(self.app)
        self.login(self.client, self.store.invite('Tester'))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def login(self, client, token):
        r=client.post('/api/login',json={'code':token})
        self.assertEqual(r.status_code,200,r.text)
        client.headers['X-CSRF-Token']=r.json()['csrf']

    def project(self):
        r=self.client.post('/api/projects',json={'title':'Test trip','request':'Highlight the visible person.'})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()['id']

    def photo(self, color='orange'):
        buffer=io.BytesIO()
        Image.new('RGB',(100,80),color).save(buffer,format='JPEG')
        return buffer.getvalue()

    def begin(self,p,data,name='photo.jpg',kind='photo'):
        r=self.client.post(f'/api/projects/{p}/uploads',json={'name':name,'size':len(data),'kind':kind})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()['id']

    def upload(self,p,data,name='photo.jpg',kind='photo'):
        u=self.begin(p,data,name,kind)
        r=self.client.put(f'/api/projects/{p}/uploads/{u}?offset=0',content=data)
        self.assertEqual(r.status_code,200,r.text)
        r=self.client.post(f'/api/projects/{p}/uploads/{u}/complete')
        self.assertEqual(r.status_code,200,r.text)
        return u

    def analyze(self,p):
        r=self.client.post(f'/api/projects/{p}/analyze',json={'request':'Highlight the visible person.'})
        self.assertEqual(r.status_code,202,r.text)
        return r.json()

    def run_fixture(self,p):
        job=self.analyze(p)
        claimed=self.store.claim()
        self.assertEqual(claimed['id'],job['job_id'])
        execute(self.settings,job['job_id'],FixtureModel())
        self.store.finish(job['job_id'],'review')
        result=self.client.get(f'/api/projects/{p}/proposal')
        self.assertEqual(result.status_code,200,result.text)
        return job,result.json()

    def test_auth_csrf_origin_and_isolation(self):
        p=self.project()
        anon=TestClient(self.app)
        self.assertEqual(anon.get('/api/projects').status_code,401)
        self.assertEqual(self.client.post('/api/projects',json={'title':'x','request':'x'},headers={'X-CSRF-Token':''}).status_code,403)
        self.assertEqual(self.client.post('/api/logout',headers={'Origin':'https://attacker.invalid'}).status_code,403)
        self.login(anon,self.store.invite('Other'))
        self.assertEqual(anon.get('/api/projects/'+p).status_code,404)
        self.assertEqual(anon.delete('/api/projects/'+p).status_code,404)
        self.assertEqual(anon.get('/api/projects').json(),[])
        anon.close()

    def test_resume_retry_integrity_and_real_decode(self):
        p=self.project(); data=self.photo();u=self.begin(p,data,'../../<script>.jpg')
        url=f'/api/projects/{p}/uploads/{u}'
        self.assertEqual(self.client.post(url+'/complete').status_code,409)
        part=data[:100]
        self.assertEqual(self.client.put(url+'?offset=0',content=part).json()['offset'],100)
        self.assertEqual(self.client.put(url+'?offset=0',content=part).json()['offset'],100)
        self.assertEqual(self.client.put(url+'?offset=0',content=b'wrong').status_code,409)
        self.assertEqual(self.client.put(url+'?offset=101',content=data[100:]).status_code,409)
        self.assertEqual(self.client.put(url+'?offset=100',content=data[100:]).status_code,200)
        complete=self.client.post(url+'/complete')
        self.assertEqual(complete.status_code,200,complete.text)
        self.assertEqual(complete.json()['sha256'],sha256(self.store.project_dir(p)/'media'/u/'original'))
        self.assertEqual(self.client.get(url+'/preview').headers['content-type'],'image/jpeg')
        self.assertEqual(self.client.post(url+'/complete').status_code,200)

    def test_size_type_invalid_media_and_mixed_inputs(self):
        p=self.project();u=self.begin(p,b'not a picture')
        self.client.put(f'/api/projects/{p}/uploads/{u}?offset=0',content=b'not a picture')
        self.assertEqual(self.client.post(f'/api/projects/{p}/uploads/{u}/complete').status_code,422)
        self.assertEqual(self.client.post(f'/api/projects/{p}/analyze',json={'request':'x'}).status_code,409)
        self.assertEqual(self.client.post(f'/api/projects/{p}/uploads',json={'name':'x.mov','size':10,'kind':'video'}).status_code,409)
        self.assertEqual(self.client.post(f'/api/projects/{p}/uploads',json={'name':'big.jpg','size':21*1024*1024,'kind':'photo'}).status_code,413)
        self.assertEqual(self.client.put(f'/api/projects/{p}/uploads/{u}?offset=0',content=b'x'*(self.settings.chunk_size+1)).status_code,413)
        self.assertEqual(self.client.delete(f'/api/projects/{p}/uploads/{u}').status_code,200)

    def test_decode_limits_are_reviewable_errors(self):
        p=self.project();data=self.photo();u=self.begin(p,data)
        url=f'/api/projects/{p}/uploads/{u}'
        self.client.put(url+'?offset=0',content=data)
        with patch('PIL.Image.MAX_IMAGE_PIXELS',100):
            result=self.client.post(url+'/complete')
        self.assertEqual(result.status_code,422,result.text)
        self.assertIn('50 million pixels',result.json()['detail'])
        p2=self.project();v=self.begin(p2,b'invalid-video','trip.mp4','video')
        url=f'/api/projects/{p2}/uploads/{v}'
        self.client.put(url+'?offset=0',content=b'invalid-video')
        with patch('trip_upload.media.subprocess.run',side_effect=subprocess.TimeoutExpired('ffprobe',60)):
            result=self.client.post(url+'/complete')
        self.assertEqual(result.status_code,422,result.text)
        self.assertIn('timed out',result.json()['detail'])

    def test_photo_roundtrip_approval_and_stale_revision(self):
        p=self.project();self.upload(p,self.photo())
        job,result=self.run_fixture(p);prop=result['proposal']
        self.assertEqual(prop['provenance']['model']['provider'],'explicit_test_double')
        self.assertIsNone(prop['moments'][0]['hero_timestamp_s'])
        self.assertIsNone(prop['moments'][0]['clip'])
        self.assertIsNone(prop['moments'][0]['references'][0]['timestamp_s'])
        image=prop['moments'][0]['image']
        self.assertEqual(self.client.get(f'/api/projects/{p}/artifacts/{image}').status_code,200)
        self.assertEqual(self.client.get(f'/api/projects/{p}/artifacts/intent/intent.json').status_code,404)
        approval={**job,'proposal_sha256':result['sha256'],'moment_ids':[prop['moments'][0]['id']],
                  'style':'natural','lighting':'day'}
        r=self.client.post(f'/api/projects/{p}/approve',json=approval)
        self.assertEqual(r.status_code,200,r.text)
        self.assertFalse(r.json()['approval']['generation_started'])
        self.assertFalse(r.json()['generation_available'])
        self.analyze(p)
        self.assertEqual(self.client.post(f'/api/projects/{p}/approve',json=approval).status_code,409)
        self.assertIsNone(self.client.get(f'/api/projects/{p}').json()['approval'])

    def test_generation_is_bound_to_approval_and_protects_active_inputs(self):
        from trip_upload.generation import execute as generate
        p=self.project();self.upload(p,self.photo());job,result=self.run_fixture(p)
        with patch('trip_upload.app.generation_available',return_value=True):
            self.assertEqual(self.client.post(f'/api/projects/{p}/generate').status_code,409)
            approval={**job,'proposal_sha256':result['sha256'],'moment_ids':[result['proposal']['moments'][0]['id']],
                      'style':'cinematic','lighting':'night'}
            self.assertEqual(self.client.post(f'/api/projects/{p}/approve',json=approval).status_code,200)
            response=self.client.post(f'/api/projects/{p}/generate')
            self.assertEqual(response.status_code,202,response.text)
            gid=response.json()['generation_id']
            self.assertEqual(self.client.post(f'/api/projects/{p}/generate').status_code,409)
            self.assertEqual(self.client.post(f'/api/projects/{p}/approve',json=approval).status_code,409)
            self.assertEqual(self.client.post(f'/api/projects/{p}/analyze',json={'request':'changed'}).status_code,409)
            self.assertEqual(self.client.delete(f'/api/projects/{p}').status_code,409)
            stranger=TestClient(self.app);self.login(stranger,self.store.invite('Other'))
            self.assertEqual(stranger.get(f'/api/projects/{p}/generations/{gid}/result').status_code,404)
            stranger.close()
            self.store.claim_generation()
            # Refuse changed source data before any GPU subprocess runs.
            with self.store.db() as db:
                u=db.execute('SELECT id FROM uploads WHERE project=?',(p,)).fetchone()['id']
            (self.store.project_dir(p)/'media'/u/'original').write_bytes(b'changed')
            with patch('trip_upload.generation.subprocess.run') as invoked:
                with self.assertRaisesRegex(ValueError,'source hash changed'):
                    generate(self.settings,gid)
                invoked.assert_not_called()
            self.store.finish_generation(gid,'Test failure')
            self.assertEqual(self.client.get(f'/api/projects/{p}').json()['generation']['id'],gid)
            approval['lighting']='day'
            self.assertEqual(self.client.post(f'/api/projects/{p}/approve',json=approval).status_code,200)
            self.assertIsNone(self.client.get(f'/api/projects/{p}').json()['generation'])
            retry=self.client.post(f'/api/projects/{p}/generate').json()['generation_id']
            self.client.post(f'/api/projects/{p}/generations/{retry}/cancel')
            self.assertIsNone(self.store.claim_generation())

    def test_video_roundtrip_uses_existing_skill_contract(self):
        video=Path(self.tmp.name)/'sample.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=128x96:rate=10',
                        '-t','2','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
        p=self.project();self.upload(p,video.read_bytes(),'sample.mov','video')
        job,result=self.run_fixture(p)
        prop=result['proposal']
        self.assertIsInstance(prop['moments'][0]['hero_timestamp_s'],float)
        folder=self.store.job_dir(p,job['job_id'])
        self.assertTrue((folder/'evidence/catalog.json').exists())
        clip=folder/prop['moments'][0]['clip']
        streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(clip)]))['streams']
        self.assertEqual([s['codec_type'] for s in streams],['video'])

    def test_cancel_recovery_and_delete(self):
        p=self.project();self.upload(p,self.photo());job=self.analyze(p)
        self.assertEqual(self.client.delete('/api/projects/'+p).status_code,409)
        self.client.post(f'/api/projects/{p}/cancel')
        self.assertIsNone(self.store.claim())
        self.assertEqual(self.client.get('/api/projects/'+p).json()['status'],'cancelled')
        job=self.analyze(p);self.store.claim();self.store.recover()
        self.assertEqual(self.client.get('/api/projects/'+p).json()['status'],'failed')
        self.assertEqual(self.client.delete('/api/projects/'+p).status_code,200)
        self.assertFalse(self.store.project_dir(p).exists())

    def test_source_hash_change_fails_before_inference(self):
        p=self.project();u=self.upload(p,self.photo());job=self.analyze(p);self.store.claim()
        (self.store.project_dir(p)/'media'/u/'original').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum changed'):
            execute(self.settings,job['job_id'],FixtureModel())

    def test_heic_and_orientation(self):
        import pillow_heif
        image=Image.new('RGB',(90,60),'green');exif=Image.Exif();exif[274]=6
        buffer=io.BytesIO();image.save(buffer,format='JPEG',exif=exif)
        p=self.project();u=self.upload(p,buffer.getvalue())
        with Image.open(self.store.project_dir(p)/'media'/u/'normalized.jpg') as normalized:
            self.assertEqual(normalized.size,(60,90))
        buffer=io.BytesIO();image.save(buffer,format='HEIF')
        self.upload(p,buffer.getvalue(),'phone.heic')

    def test_login_rate_limit_persists_failures(self):
        anon=TestClient(self.app)
        for _ in range(15):
            self.assertEqual(anon.post('/api/login',json={'code':'wrong-code-123456'}).status_code,401)
        self.assertEqual(anon.post('/api/login',json={'code':'wrong-code-123456'}).status_code,429)
        anon.close()


if __name__=='__main__':
    unittest.main()
