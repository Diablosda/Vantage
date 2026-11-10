import test_environment
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.paths import data_root,cache_root,asset_file
from backend.portable import create_bundle,read_bundle
class PathTests(unittest.TestCase):
 def test_defaults_and_overrides_do_not_depend_on_install_directory(self):
  with patch.dict(os.environ,{'LOCALAPPDATA':'C:/Example/Local'},clear=True):
   self.assertEqual(data_root(),Path('C:/Example/Local/Vantage/Data'));self.assertEqual(cache_root(),Path('C:/Example/Local/Vantage/Cache'))
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   with patch.dict(os.environ,{'VANTAGE_DATA_DIR':tmp,'VANTAGE_CACHE_DIR':tmp}):self.assertEqual(data_root(),Path(tmp).resolve());self.assertEqual(cache_root(),Path(tmp).resolve())
 def test_legacy_asset_is_read_only_and_new_data_has_priority(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   root=Path(tmp);old=root/'install';data=root/'Data';(old/'model').mkdir(parents=True);(old/'model'/'a.glb').write_bytes(b'old')
   self.assertEqual(asset_file('model','a.glb',data,old),(old/'model'/'a.glb').resolve());self.assertFalse(data.exists())
   (data/'model').mkdir(parents=True);(data/'model'/'a.glb').write_bytes(b'new');self.assertEqual(asset_file('model','a.glb',data,old),(data/'model'/'a.glb').resolve());self.assertEqual((old/'model'/'a.glb').read_bytes(),b'old')
   with self.assertRaises(ValueError):asset_file('model','../secret',data,old)
 def test_legacy_bundle_migrates_assets_into_new_user_store(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   root=Path(tmp);old=root/'install';data=root/'Data';new=root/'new-user';(old/'model').mkdir(parents=True);(old/'model'/'a.glb').write_bytes(b'model');p={'objects':[{'modelSource':{'name':'a.glb'}}]};dest=root/'project.zip'
   create_bundle(p,dest,data,legacy_root=old);self.assertEqual(read_bundle(dest.read_bytes(),new),p);self.assertEqual((new/'model'/'a.glb').read_bytes(),b'model');self.assertFalse(data.exists())
