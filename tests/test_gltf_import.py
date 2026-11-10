import test_environment
import os
import io, json, struct, tempfile, time, unittest, zipfile
from pathlib import Path
import server

class GltfImportTests(unittest.TestCase):
 def test_zip_with_external_buffer_converts_to_glb(self):
  server.RUNTIME.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
   folder=Path(folder);old=server.DATA
   # Worker writes only to a temporary model library.
   server.DATA=folder
   try:
    data=struct.pack('<9f3H',0,0,0,1,0,0,0,1,0,0,1,2)
    doc={'asset':{'version':'2.0'},'buffers':[{'uri':'triangle.bin','byteLength':len(data)}],'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':36,'target':34962},{'buffer':0,'byteOffset':36,'byteLength':6,'target':34963}],'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3','min':[0,0,0],'max':[1,1,0]},{'bufferView':1,'componentType':5123,'count':3,'type':'SCALAR'}],'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],'nodes':[{'mesh':0}],'scenes':[{'nodes':[0]}],'scene':0}
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as z:z.writestr('mesh/model.gltf',json.dumps(doc));z.writestr('mesh/triangle.bin',data)
    # Keep the worker script path anchored in the actual installation.
    server.DATA=old
    existing={p.name for p in (old/'model').glob('*.glb')}
    jobid=server.submit({'mode':'convert','kind':'zip'},raw.getvalue());job=server.JOBS[jobid]
    for _ in range(600):
     if job['state'] in ('done','error'):break
     time.sleep(.1)
    self.assertEqual(job['state'],'done',job['message']);target=old/'model'/job['result']['name']
    try:self.assertEqual(target.read_bytes()[:4],b'glTF')
    finally:
     if target.name not in existing:target.unlink(missing_ok=True)
   finally:server.DATA=old
 def test_resource_path_escape_is_rejected(self):
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:z.writestr('../escape.gltf','{}')
  jobid=server.submit({'mode':'convert','kind':'zip'},raw.getvalue());job=server.JOBS[jobid]
  for _ in range(600):
   if job['state'] in ('done','error'):break
   time.sleep(.1)
  self.assertEqual(job['state'],'error');self.assertIn('无效路径',job['message'])
if __name__=='__main__':unittest.main()
