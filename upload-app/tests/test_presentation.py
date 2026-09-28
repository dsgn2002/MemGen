import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trip_upload.presentation import attach_presentation

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
