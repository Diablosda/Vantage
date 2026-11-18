import test_environment
import os
import json,subprocess,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.model import validate
from backend.segments import Evaluator,camera_quaternion
from test_web_backend import fixture

def segmented():
 p=fixture();p['settings']['duration']=1;actor,cam,target=p['objects'];actor['orientation']='PATH';actor['smooth']=True
 for o in p['objects']:o['segments']=[]
 actor['nodes']=[dict(id='a',position=[0,0,0],time=0,dwell=0,radius=.2),dict(id='b',position=[.5,0,0],time=.5,dwell=0,radius=.2),dict(id='c',position=[.5,.5,0],time=1,dwell=0,radius=.2)]
 actor['segments']=[dict(id='s1',start='a',end='b',startTime=0,endTime=.5),dict(id='s2',start='b',end='c',startTime=.5,endTime=1)]
 target.update(follow=actor['id'],offset=[0,0,.3]);cam['position']=[2,0,.3]
 cfg=dict(owner=actor['id'],focusTarget=actor['id'],focusLocal=[0,0,.3],inherit=False,start=dict(position=[2,0,.3],lens=40,roll=0),motion='ORBIT',axis='X',speed=1,direction=1,tilt=90,radius=2,lens=40,roll=0)
 cam['shots']={'s1':cfg,'s2':dict(cfg,inherit=True,motion='TRANSLATE',axis='Z')};return p
class SegmentBackendTests(unittest.TestCase):
 def test_validation_and_disconnected_save(self):
  p=segmented();self.assertEqual(validate(p,True),[])
  p['objects'][0]['segments'].append(dict(id='s3',start='a',end='c',startTime=0,endTime=1));self.assertTrue(validate(p,True))
 def test_conflict_is_not_silently_repaired(self):
  p=segmented();p['objects'][1]['shots']['s1']['radius']=10
  self.assertFalse(validate(p));self.assertTrue(any('冲突' in e for e in validate(p,True)))
 def test_native_render_roundtrip_and_sample_parity(self):
  self.verify_native(segmented())
 def test_v12_validation_and_legacy_defaults(self):
  p=segmented();cfg=p['objects'][1]['shots']['s1'];cfg.update(motion='DIAGONAL',orientation='FREE',velocity=[1,-2,.5],rotationDelta=[.2,-.4,7])
  self.assertEqual(validate(p),[])
  for key,value in [('velocity',[1,2]),('rotationDelta',[0,float('nan'),0]),('orientation','INVALID')]:
   original=cfg[key];cfg[key]=value;self.assertTrue(validate(p));cfg[key]=original
  cfg['start']['quaternion']=[0,0,0,0];self.assertTrue(validate(p));cfg['start']['quaternion']=[0,0,0,1];self.assertFalse(validate(p))
  cfg.update(motion='DOLLY',orientation='LOCK',speed=100);self.assertTrue(any('推进' in e for e in validate(p,True)))
 def test_v12_native_combined_motion_roundtrip_and_render(self):
  p=segmented();actor,cam,target=p['objects'];actor['smooth']=False
  actor['nodes']=[dict(id=f'n{i}',position=[i*.25,0,0],time=i*.25,dwell=0,radius=.2) for i in range(5)]
  actor['segments']=[dict(id=f's{i}',start=f'n{i}',end=f'n{i+1}',startTime=i*.25,endTime=(i+1)*.25) for i in range(4)]
  import copy
  template=copy.deepcopy(cam['shots']['s1']);cam['shots']={}
  for i,motion in enumerate(['DIAGONAL','DOLLY','ORBIT','ORBIT']):
   cfg=copy.deepcopy(template);cfg.update(motion=motion,orientation='LOCK' if i==2 else 'FREE',velocity=[.1,-.3,.2],rotationDelta=[.2,-.1,.4],speed=.5,direction=-1,tilt=0,inherit=i in (1,3))
   cfg['start']['position']=[i*.25+2,0,.3];cfg['start']['quaternion']=list(camera_quaternion(dict(position=cfg['start']['position'],focus=[i*.25,0,.3],roll=0)))
   cam['shots'][f's{i}']=cfg
  self.assertEqual(validate(p,True),[]);self.verify_native(p)
 def test_v13_native_horizontal_orbit_poles_and_roundtrip(self):
  p=segmented();actor,cam,target=p['objects']
  for i,cfg in enumerate(cam['shots'].values()):
   cfg.update(controlVersion=3,inherit=False,motion='ORBIT',orientation='LOCK',orbitAngle=120,azimuth=0,tilt=0,radius=2,rotationDelta=[0,0,.2])
   cfg['start']=dict(position=[2+i,0,2],quaternion=[0,0,0,1],lens=40,roll=0)
  self.assertEqual(validate(p,True),[]);self.verify_native(p)
  for height in [-3,.3,5]:
   cfg=cam['shots']['s1'];cfg['start']['position']=[0,0,height];cfg['radius']=0
   self.assertEqual(validate(p,True),[])
   state=Evaluator(p).camera(cam,0);self.assertEqual(tuple(state['position']),(0,0,height));self.assertTrue(all(__import__('math').isfinite(v) for v in camera_quaternion(state)))
 def test_full_film_multiple_shots_native_export(self):
  p=segmented();p['shotFramework']=2
  for i,cfg in enumerate(p['objects'][1]['shots'].values()):
   cfg.update(mode='FREE',orientation='FREE',inherit=False,motion='DIAGONAL',velocity=[.1,0,0],focusWorld=[0,0,.3])
   cfg['start']=dict(position=[3+i*2,-4,3],quaternion=[0,0,0,1],lens=40,roll=0)
  self.assertEqual(validate(p,True),[]);self.verify_native(p)
 def verify_native(self,p):
  with tempfile.TemporaryDirectory(prefix='.segment_verify_',dir=ROOT) as d:
   work=Path(d);(work/'p.json').write_text(json.dumps(p),encoding='utf8')
   script=work/'verify.py';script.write_text('''import sys,json,bpy
from pathlib import Path
from mathutils import Quaternion
root=Path(sys.argv[sys.argv.index('--')+1]);sys.path.insert(0,str(root));work=Path(__file__).parent
from backend.blender_worker import build,import_scene
from backend.segments import Evaluator,shot_range
from ai_previs import runtime
p=json.loads((work/'p.json').read_text());scene=build(p);ev=Evaluator(p)
for frame in [1,4,7,10,12,4]:
 scene.frame_set(frame);runtime.evaluate(scene,True);t=shot_range(p)[0]+(frame-1)/p['settings']['fps']
 for ob in runtime.controls(scene):
  data=ev.objects[ob['previs_id']];state=ev.camera(data,t) if data['role']=='CAMERA' else ev.pose(data,t)
  assert max(abs(a-b) for a,b in zip(ob.location,state['position']))<1e-5
  assert abs(abs(ob.rotation_euler.to_quaternion().dot(runtime.portable_rotation(state)))-1)<1e-5
scene.previs.project_path=str(work/'scene.blend');scene.previs.output_path=str(work/'video.mp4')
runtime.prepare_export(scene);animated=runtime.bake(scene);bpy.ops.wm.save_as_mainfile(filepath=str(work/'scene.blend'),check_existing=False);bpy.ops.render.render(animation=True);runtime.clear_bake(animated)
assert scene.frame_end==round((shot_range(p)[1]-shot_range(p)[0])*p['settings']['fps'])
assert import_scene({'source':str(work/'scene.blend')})['project']==p
''',encoding='utf8')
   r=subprocess.run([str(ROOT.parent/'blender/blender-5.2.2-windows-x64/blender.exe'),'-b','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(script),'--',str(ROOT)],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=120)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertGreater((work/'video.mp4').stat().st_size,1000)
 def test_framework_dwell_export_global_time_and_roundtrip(self):
  import copy
  p=segmented();a,c,t=p['objects'];p['shotFramework']=2;p['settings']['duration']=1.5
  a['nodes'][1]['dwell']=.5;a['nodes'][2]['time']=1.5;a['segments'][1].update(startTime=1,endTime=1.5)
  b=copy.deepcopy(a);b.update(id='other',name='other');b['nodes']=[dict(n,id='other-'+n['id']) for n in b['nodes']]
  b['nodes'][1]['dwell']=0;b['nodes'][2]['time']=1
  b['segments']=[dict(s,id='other-'+s['id'],start='other-'+s['start'],end='other-'+s['end']) for s in b['segments']];b['segments'][1].update(startTime=.5,endTime=1)
  p['objects'].append(b)
  cfg=c['shots']['s1'];cfg.update(mode='FREE',focusWorld=[0,0,.3],orientation='FREE',motion='DIAGONAL',velocity=[.5,0,0],rotationDelta=[.1,0,0],lensEnd=60)
  cfg['start']['quaternion']=[0,0,0,1];c['shots']={'b':cfg}
  cfg['freeMotion']=dict(id=c['id'],position=[2,0,.3],rotation=[0,0,0],scale=[1,1,1],nodes=[dict(id='c0',position=[2,0,.3],time=0,dwell=0),dict(id='c1',position=[3,0,.3],time=1.5,dwell=0)],segments=[dict(id='cs',start='c0',end='c1',startTime=0,endTime=1.5)],angles=[dict(time=.5,rotation=[0,0,0]),dict(time=1,rotation=[0,0,.2])],lenses=[dict(time=.5,value=40),dict(time=1,value=60)])
  cfg['aimMotion']=dict(position=[0,0,.3],nodes=[dict(id='t0',position=[0,0,.3],time=0),dict(id='t1',position=[0,1,.6],time=.5)],segments=[dict(id='ts',start='t0',end='t1',startTime=0,endTime=.5)])
  self.assertEqual(validate(p,True),[]);self.verify_native(p)
if __name__=='__main__':unittest.main()
