import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trip_upload.presentation import attach_presentation, inherited_manifest

class PresentationTests(unittest.TestCase):
    def test_source_bound_refinement_preserves_generation_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'presentation.json'
            result = {'assets':[{'id':'moment-1','source_sha256':'source','mesh_sha256':'mesh'}],
                      'timing':{'generation_seconds':12}}
            self.assertEqual(attach_presentation(copy.deepcopy(result), path), result)
            edit = {'id':'moment-1','source_sha256':'source','mesh_sha256':'mesh','preset':'dining-characters-v1'}
            path.write_text(json.dumps({'version':1,'assets':[edit]}))
            actual = attach_presentation(copy.deepcopy(result), path)
            self.assertEqual(actual['timing'], result['timing'])
            self.assertEqual(actual['assets'][0]['presentation']['preset'], edit['preset'])
            for key, value in [('source_sha256','other'),('mesh_sha256','other'),('id','other'),('preset','external-script')]:
                path.write_text(json.dumps({'version':1,'assets':[{**edit,key:value}]}))
                with self.assertRaises(ValueError):
                    attach_presentation(copy.deepcopy(result), path)

    def test_repeat_generation_keeps_preset_only_for_same_approved_source(self):
        approval = {'job_id':'job', 'revision':3, 'proposal_sha256':'proposal',
                    'moment_ids':['moment-1'], 'style':'cinematic', 'lighting':'night'}
        old = {'assets':[{'id':'moment-1','source_sha256':'source','mesh_sha256':'old-mesh'}]}
        new = {'assets':[{'id':'moment-1','source_sha256':'source','mesh_sha256':'new-mesh'}]}
        previous = {'version':1,'assets':[{'id':'moment-1','source_sha256':'source',
                                          'mesh_sha256':'old-mesh','preset':'dining-characters-v1'}]}
        manifest = inherited_manifest(old, previous, {**approval,'notes':'earlier note'},
                                      new, {**approval,'notes':''}, 'earlier-generation')
        self.assertEqual(manifest['assets'][0]['mesh_sha256'],'new-mesh')
        self.assertEqual(manifest['reused_from_generation'],'earlier-generation')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'presentation.json'
            path.write_text(json.dumps(manifest))
            self.assertEqual(attach_presentation(copy.deepcopy(new),path)['assets'][0]
                             ['presentation']['preset'],'dining-characters-v1')
        self.assertIsNone(inherited_manifest(old, previous, approval,
            {'assets':[{'id':'moment-1','source_sha256':'different','mesh_sha256':'new-mesh'}]},
            approval,'earlier-generation'))
        self.assertIsNone(inherited_manifest(old, previous, approval,new,
            {**approval,'style':'natural'},'earlier-generation'))
        self.assertIsNone(inherited_manifest(old, {**previous,'assets':[
            {**previous['assets'][0],'mesh_sha256':'incorrect'}]},approval,new,approval,
            'earlier-generation'))
