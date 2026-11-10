import test_environment
import os
import json, hashlib, tempfile, unittest
from pathlib import Path
from backend.portable import create_bundle, read_bundle

class BundleTests(unittest.TestCase):
 def test_roundtrip_and_collision(self):
  Path(os.environ['VANTAGE_CACHE_DIR']).mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=Path(os.environ['VANTAGE_CACHE_DIR']).resolve()) as d:
   root=Path(d);source=root/'src';target=root/'dst';(source/'model').mkdir(parents=True);(source/'动作').mkdir();(target/'model').mkdir(parents=True)
   model=b'first model';motion=b'animation';name=hashlib.sha256(motion).hexdigest()+'.glb'
   (source/'model'/'x.glb').write_bytes(model);(source/'动作'/name).write_bytes(motion);(target/'model'/'x.glb').write_bytes(b'existing data')
   project={'version':2,'objects':[{'modelSource':{'name':'x.glb','center':[0,0,0]},'segments':[{'motion':{'name':name}}]}],'shots':{'a':1}}
   archive=root/'a.zip';create_bundle(project,archive,source);restored=read_bundle(archive.read_bytes(),target)
   resolved=restored['objects'][0]['modelSource']['name'];self.assertNotEqual(resolved,'x.glb');self.assertEqual((target/'model'/resolved).read_bytes(),model);self.assertEqual((target/'model'/'x.glb').read_bytes(),b'existing data');self.assertEqual((target/'动作'/name).read_bytes(),motion);self.assertEqual(restored['shots'],project['shots'])
 def test_oversized_bundle_is_rejected_before_writing(self):
  from unittest.mock import patch
  Path(os.environ['VANTAGE_CACHE_DIR']).mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=Path(os.environ['VANTAGE_CACHE_DIR']).resolve()) as d:
   root=Path(d);(root/'model').mkdir();(root/'model'/'large.glb').write_bytes(b'x'*1024)
   project={'objects':[{'modelSource':{'name':'large.glb'}}]};destination=root/'out.zip'
   with patch('backend.portable.MAX_ARCHIVE',512):
    with self.assertRaisesRegex(ValueError,'工程包超过'):create_bundle(project,destination,root)
   self.assertFalse(destination.exists())
 def test_unexpected_file_rejected(self):
  from zipfile import ZipFile
  import io
  b=io.BytesIO()
  with ZipFile(b,'w') as z:z.writestr('project.previs','{"objects":[]}');z.writestr('../bad','x')
  with self.assertRaises(ValueError):read_bundle(b.getvalue(),Path('.'))
if __name__=='__main__':unittest.main()
