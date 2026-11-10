import test_environment
import os
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
import server

def glb(nodes, animated=False):
    value={'asset':{'version':'2.0'},'nodes':nodes,'skins':[{'joints':[1]}]}
    if animated:value['animations']=[{'name':'Walk','channels':[{'target':{'node':1,'path':'rotation'}}]}]
    data=json.dumps(value).encode();data+=b' '*((-len(data))%4)
    return struct.pack('<4sII',b'glTF',2,20+len(data))+struct.pack('<I4s',len(data),b'JSON')+data

class MotionImportTests(unittest.TestCase):
    def setUp(self):
        Path(os.environ['VANTAGE_CACHE_DIR']).mkdir(exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=Path(os.environ['VANTAGE_CACHE_DIR']).resolve());self.original=server.DATA;server.DATA=Path(self.tmp.name)
        (server.DATA/'model').mkdir();self.nodes=[{'name':'Root','children':[1]},{'name':'Bone','rotation':[0,0,0,1]}]
        (server.DATA/'model'/'person.glb').write_bytes(glb(self.nodes))
    def tearDown(self):server.DATA=self.original;self.tmp.cleanup()
    def post(self,body):
        handler=object.__new__(server.Handler);handler.headers={'Host':'127.0.0.1:1234','X-Previs-Token':server.TOKEN,'Content-Length':str(len(body))}
        handler.server=type('S',(),{'server_port':1234})();handler.path='/api/motions?model=person.glb';handler.rfile=io.BytesIO(body);result=[]
        handler.json=lambda value,status=200:result.append((status,value));handler.do_POST();return result[0]
    def test_compatible_action_is_stored(self):
        status,result=self.post(glb(self.nodes,True));self.assertEqual(status,200);self.assertTrue((server.DATA/'动作'/result['name']).is_file())
    def test_incompatible_rest_pose_is_rejected(self):
        status,result=self.post(glb([self.nodes[0],{'name':'Bone','rotation':[0,1,0,0]}],True));self.assertEqual(status,400);self.assertIn('骨架',result['error'])
if __name__=='__main__':unittest.main()
