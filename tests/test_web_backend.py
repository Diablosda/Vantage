import test_environment
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.model import validate

def obj(ident,role='PROP'):
    return dict(id=ident,name=ident,role=role,position=[0,0,0],rotation=[0,0,0],scale=[1,1,1],nodes=[],angles=[],lenses=[],rolls=[],parts=[],orientation='FIXED')
def fixture():
    actor=obj('temporary geometry');actor['parts']=[dict(shape='BOX',matrix=[1,0,0,0,0,.6,0,0,0,0,.8,0,0,0,0,1])]
    actor['nodes']=[dict(position=[0,0,0],time=0,dwell=0,radius=.2,exact=False,easing='LINEAR'),dict(position=[.65,0,0],time=.4,dwell=0,radius=.2,exact=False,easing='IN_OUT')]
    cam=obj('camera','CAMERA');cam.update(position=[4,-6,3],lens=40,controlScale=.2,viewMode='LOCK',target='target')
    target=obj('target','TARGET');target['position']=[0,0,.3]
    return dict(version=2,id='engineering',name='temporary-engineering-check',settings=dict(fps=12,duration=.5,width=192,height=144,grid=.5),activeCamera='camera',objects=[actor,cam,target])

class ModelTests(unittest.TestCase):
    def test_valid_scene(self):self.assertEqual(validate(fixture(),True),[])
    def test_locator_color_validation(self):
        p=fixture();p['objects'][0]['locatorColor']='#12aBcF';self.assertEqual(validate(p),[])
        p['objects'][0]['locatorColor']='red';self.assertTrue(any('定位颜色' in e for e in validate(p)))
    def test_missing_target(self):
        p=fixture();p['objects'][1]['target']='missing';self.assertTrue(validate(p,True))
    def test_invalid_geometry(self):
        p=fixture();p['objects'][0]['parts']=[dict(shape='MESH',matrix=[1]*16,vertices=[[0,0,0]],triangles=[[0,1,2]])];self.assertTrue(validate(p))
    def test_odd_size_and_empty_save(self):
        p=fixture();p['settings']['width']=193;self.assertTrue(validate(p,True));p['objects']=[];p['activeCamera']=None;self.assertEqual(validate(p),[])
    def test_duplicate_times(self):
        p=fixture();p['objects'][1]['lenses']=[dict(time=0,value=30),dict(time=0,value=60)];self.assertTrue(validate(p))
    def test_real_worker_roundtrip_and_mp4(self):
        blender=ROOT.parent/'blender'/'blender-5.2.2-windows-x64'/'blender.exe'
        with tempfile.TemporaryDirectory(prefix='.web_backend_',dir=ROOT) as folder:
            work=Path(folder);project=fixture();task=work/'task.json';blend=work/'result.blend';video=work/'result.mp4'
            def run(payload):
                task.write_text(json.dumps(payload),encoding='utf-8')
                result=subprocess.run([str(blender),'--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(ROOT/'backend'/'blender_worker.py'),'--',str(task)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                return json.loads((work/'result.json').read_text(encoding='utf-8'))
            self.assertTrue(run(dict(mode='render',project=project,blend=str(blend),video=str(video)))['saved'])
            self.assertGreater(video.stat().st_size,1000)
            self.assertEqual(run(dict(mode='import',source=str(blend)))['project'],project)
            ffmpeg=ROOT.parent/'blender'/'tools'/'ffmpeg'/'ffmpeg.exe'
            decoded=subprocess.run([str(ffmpeg),'-v','info','-i',str(video),'-f','null','-'],capture_output=True,text=True,errors='replace')
            self.assertEqual(decoded.returncode,0,decoded.stderr);self.assertIn('192x144',decoded.stderr);self.assertIn('h264',decoded.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
