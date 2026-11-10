"""Fetch the pinned public dependency, verify npm integrity, retain only runtime files."""
import base64, hashlib, io, json, tarfile, urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
version=json.loads((root/'package.json').read_text())['dependencies']['three']
meta=json.load(urllib.request.urlopen('https://registry.npmjs.org/three/'+version,timeout=30))
data=urllib.request.urlopen(meta['dist']['tarball'],timeout=60).read()
algorithm,expected=meta['dist']['integrity'].split('-',1)
assert algorithm=='sha512' and base64.b64encode(hashlib.sha512(data).digest()).decode()==expected
files=['build/three.module.js','build/three.core.js','examples/jsm/controls/OrbitControls.js','examples/jsm/controls/TransformControls.js','examples/jsm/loaders/GLTFLoader.js','examples/jsm/utils/BufferGeometryUtils.js','LICENSE']
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
    for name in files:
        out=root/'web'/'vendor'/'three'/name;out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(archive.extractfile('package/'+name).read())
print('Verified Three.js '+version+'; local runtime files ready')
