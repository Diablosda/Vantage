import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mergePaths,deletePathRange,SegmentMotion,pathErrors,videoTrackOrder,shotAt,migrate,configureShot,currentShot,Evaluator,setDwell,setUnitDuration,units,splitSegment,pruneCurrentShot,upgradeFramework,appendPoint,newShot} from '../web/segments.js';
const object=(id,role)=>({id,name:id,role,position:[0,0,0],rotation:[0,0,0],scale:[1,1,1],parts:[],nodes:[],angles:[],lenses:[],rolls:[],orientation:'FIXED'});
function fixture(){
 const a=object('a','PROP'),b=object('b','PROP'),c=object('c','CAMERA');
 for(const o of [a,b])o.nodes=[0,1,2].map(i=>({position:[i*2,o===a?0:3,0],time:i*2,dwell:0,radius:0}));
 Object.assign(c,{position:[6,-8,5],lens:50,viewMode:'FREE'});
 const p=migrate({version:2,shotFramework:2,name:'framework',activeCamera:'c',objects:[a,b,c],settings:{duration:10,fps:12,width:192,height:144,grid:.5}});
 return {p,a,b,c};
}
test('dwell and segment timing preserve movement duration; other objects keep global time',()=>{
 const {p,a,b,c}=fixture();setDwell(a,a.nodes[1],3);assert.equal(a.nodes[2].time,7);
 const cfg=configureShot(p,c,a,a.nodes[1].id,'FREE');cfg.velocity=[1,0,0];cfg.motion='DIAGONAL';cfg.lensEnd=80;
 const ev=new Evaluator(p);assert.deepEqual(ev.pose(a,3).position,[2,0,0]);assert.deepEqual(ev.pose(b,3).position,[3,3,0]);
 assert.deepEqual(ev.camera(c,3).position,[7,-8,5]);assert.equal(ev.camera(c,3).lens,60);
 setUnitDuration(a,a.segments[0].id,4);assert.equal(currentShot(p).unit.startTime,4);assert.equal(a.nodes[2].time,9);
 setDwell(a,a.nodes[1],0);pruneCurrentShot(p);assert.equal(currentShot(p),null);
});
test('retention and inheritance snapshot previous end; paths and base camera remain unchanged',()=>{
 const {p,a,b,c}=fixture(),before=JSON.stringify([a,b]);let cfg=configureShot(p,c,a,a.segments[0].id,'FREE');cfg.motion='DIAGONAL';cfg.velocity=[1,2,0];cfg.lensEnd=80;
 const end=new Evaluator(p).camera(c,2,a.segments[0].id),old=cfg;
 cfg=configureShot(p,c,b,b.segments[1].id,'FREE',true);assert.deepEqual(cfg.start.position,end.position);assert.equal(cfg.lens,80);assert.equal(Object.keys(c.shots).length,2);
 old.velocity[0]=100;assert.equal(cfg.velocity[0],1);assert.equal(JSON.stringify([a,b]),before); // no path edits
 cfg=configureShot(p,c,a,a.segments[0].id,'FREE');assert.deepEqual(cfg.start.position,c.position);assert.equal(cfg.speed,0);
 splitSegment(p,a,a.segments[0].id);assert.equal(Object.keys(c.shots).length,3);
});
test('free mode has no moving target constraint; tracking target is independent of time owner; Python parity',()=>{
 const {p,a,b,c}=fixture();setDwell(a,a.nodes[1],2);let cfg=configureShot(p,c,a,a.nodes[1].id,'TRACK');cfg.focusTarget=b.id;
 for(const mode of ['TRACK','FREE']){
  cfg.mode=mode;cfg.orientation=mode==='FREE'?'FREE':'LOCK';cfg.motion='ORBIT';cfg.orbitAngle=120;cfg.lensEnd=75;
  const ev=new Evaluator(p),samples=[2,2.5,3,4].map(t=>ev.camera(c,t));
  const r=spawnSync('python',['-c',`import json,sys\nfrom backend.model import validate\nfrom backend.segments import Evaluator,shot_range\np=json.load(sys.stdin);assert validate(p,True)==[],validate(p,True)\ne=Evaluator(p);c=e.objects['c'];assert shot_range(p)==(0,10)\nprint(json.dumps([e.camera(c,t) for t in [2,2.5,3,4]]))`],{input:JSON.stringify(p),encoding:'utf8'});
  assert.equal(r.status,0,r.stderr);const native=JSON.parse(r.stdout);samples.forEach((s,i)=>{s.position.forEach((v,j)=>assert.ok(Math.abs(v-native[i].position[j])<1e-7));assert.equal(s.lens,native[i].lens);});
 }
});
test('free path and keys use scene time, are copied independently, and match Python',()=>{
 const {p,a,c}=fixture(),cfg=configureShot(p,c,a,a.segments[1].id,'FREE'),m=cfg.freeMotion;
 appendPoint(m,[10,-8,5]);m.lenses=[{time:2,value:35},{time:4,value:85}];m.angles=[{time:2,rotation:[0,0,0]},{time:4,rotation:[0,0,1]}];
 const ev=new Evaluator(p),state=ev.camera(c,3);assert.equal(state.lens,60);assert.deepEqual(state.position,[7,-8,5]);
 const r=spawnSync('python',['-c',`import json,sys\nfrom backend.model import validate\nfrom backend.segments import Evaluator\np=json.load(sys.stdin);assert not validate(p,True),validate(p,True)\ne=Evaluator(p);print(json.dumps(e.camera(e.objects['c'],3)))`],{input:JSON.stringify(p),encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);const native=JSON.parse(r.stdout);state.cameraRotation.forEach((v,i)=>assert.ok(Math.abs(v-native.cameraRotation[i])<1e-7));assert.deepEqual(state.position,native.position);
 const next=configureShot(p,c,a,a.segments[0].id,'FREE',true);m.lenses[0].value=100;assert.equal(next.freeMotion.lenses[0].value,35);
 assert.equal(configureShot(p,c,a,a.segments[0].id,'FREE').freeMotion.nodes.length,0);
});
test('legacy migration preserves every shot and freezes inheritance',()=>{
 const {p,a,c}=fixture();delete p.shotFramework;c.shots={};for(const s of a.segments)c.shots[s.id]=newShot(p,c,a,s.id);
 c.shots[a.segments[1].id].lens=85;const original=structuredClone(p);upgradeFramework(p,3);
 assert.equal(currentShot(p).unit.id,a.segments[1].id);assert.equal(currentShot(p).cfg.lens,85);assert.equal(Object.keys(c.shots).length,2);assert.equal(Object.keys(original.objects[2].shots).length,2);
 assert.deepEqual(a.nodes,original.objects[0].nodes);
});

test('timeline keeps segment and dwell shots and selects by time regardless of editor',()=>{
 const {p,a,c}=fixture();setDwell(a,a.nodes[1],1);
 const ids=units(a).map(u=>u.id),positions=[[1,-5,3],[10,-5,3],[20,-5,3]];
 ids.forEach((sid,i)=>{const cfg=configureShot(p,c,a,sid,'FREE');cfg.start.position=positions[i];cfg.lens=30+i*20;});
 const saved=structuredClone(c.shots),times=[0,1,2,2.5,3,4.9];
 for(const id of ids){p.editShotId=id;const ev=new Evaluator(p);times.forEach(t=>assert.deepEqual(ev.camera(c,t).position,positions[t<2?0:t<3?1:2]));}
 assert.deepEqual(c.shots,saved);assert.equal(Object.keys(upgradeFramework(JSON.parse(JSON.stringify(p))).objects[2].shots).length,3);
 const r=spawnSync('python',['-c',`import json,sys
from backend.model import validate
from backend.segments import Evaluator,shot_range
p=json.load(sys.stdin);assert not validate(p,True),validate(p,True);assert shot_range(p)==(0,10)
e=Evaluator(p);print(json.dumps([e.camera(e.objects['c'],t)['position'] for t in [0,1,2,2.5,3,4.9]]))`],{input:JSON.stringify(p),encoding:'utf8'});assert.equal(r.status,0,r.stderr);assert.deepEqual(JSON.parse(r.stdout),[positions[0],positions[0],positions[1],positions[1],positions[2],positions[2]]);
});

test('free aim uses shot-local time and turns the camera independently of its path and lens',()=>{
 const {p,a,c}=fixture(),sid=a.segments[1].id,cfg=configureShot(p,c,a,sid,'FREE');
 appendPoint(cfg.freeMotion,[10,-8,5]);
 cfg.freeMotion.angles=[{time:0,rotation:[0,0,0]}];
 cfg.lensEnd=80;
 const original=new Evaluator(p).camera(c,3,sid);
 cfg.aimMotion={position:[0,0,1],nodes:[],segments:[],speed:1};
 appendPoint(cfg.aimMotion,[2,0,1]);
 const samples=[2,3,4].map(t=>new Evaluator(p).camera(c,t,sid));
 assert.deepEqual(samples.map(s=>s.focus),[[0,0,1],[1,0,1],[2,0,1]]);
 assert.deepEqual(samples[1].position,original.position);
 assert.equal(samples[1].lens,original.lens);
 for(const state of samples){
  const [x,y,z,w]=state.cameraRotation;
  const forward=[-2*(x*z+w*y),-2*(y*z-w*x),2*(x*x+y*y)-1];
  const sight=state.focus.map((n,i)=>n-state.position[i]),length=Math.hypot(...sight);
  forward.forEach((v,i)=>assert.ok(Math.abs(v-sight[i]/length)<1e-7));
 }
 const result=spawnSync('python',['-c',`import json,sys
from backend.model import validate
from backend.segments import Evaluator
p=json.load(sys.stdin);assert not validate(p,True),validate(p,True)
e=Evaluator(p);print(json.dumps([e.camera(e.objects['c'],t) for t in [2,3,4]]))`],{input:JSON.stringify(p),encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);
 JSON.parse(result.stdout).forEach((s,i)=>{assert.deepEqual(s.focus,samples[i].focus);s.cameraRotation.forEach((v,j)=>assert.ok(Math.abs(v-samples[i].cameraRotation[j])<1e-7));});
 const inherited=configureShot(p,c,a,a.segments[0].id,'FREE',true);
 assert.deepEqual(inherited.aimMotion.nodes[0].position,samples[2].focus);
 assert.deepEqual(cfg.aimMotion.nodes[0].position,[0,0,1]);
 cfg.aimMotion.nodes=[];cfg.aimMotion.segments=[];
 assert.deepEqual(new Evaluator(p).camera(c,3,sid),original);
});

test('overlapping tracks select the top camera at global time in previews and exports',()=>{
 const {p,a,b,c}=fixture();
 for(const [o,duration] of [[a,3],[b,4]]){
  o.nodes=o.nodes.slice(0,2);o.segments=o.segments.slice(0,1);
  setUnitDuration(o,o.segments[0].id,duration);
  const cfg=configureShot(p,c,o,o.segments[0].id,'FREE');
  cfg.lens=o===a?30:60;cfg.lensEnd=cfg.lens+duration;
 }
 assert.deepEqual(videoTrackOrder(c),['a','b']);
 const paths=JSON.stringify([a,b]),ev=new Evaluator(p),sid=a.segments[0].id;
 for(const [order,lenses] of [[['a','b'],[30,32.5,63,64]],[['b','a'],[60,62.5,63,64]]]){
  c.videoTracks=order;
  assert.deepEqual([0,2.5,3,4].map(t=>ev.camera(c,t).lens),lenses);
  assert.equal(ev.pose(b,3).position[0],1.5);
  assert.equal(ev.camera(c,2,sid).lens,32);
  assert.equal(shotAt(p,c,4.1),null);
  const r=spawnSync('python',['-B','-c',`import json,sys
from backend.model import validate
from backend.segments import Evaluator
from backend.export_plan import export_times,clip_times
p=json.load(sys.stdin);assert not validate(p,True),validate(p,True)
e=Evaluator(p);c=e.objects['c'];assert e.pose(e.objects['b'],3)['position'][0]==1.5
assert export_times(p)==[i/12 for i in range(48)]
a=e.objects['a'];sid=a['segments'][0]['id']
assert clip_times(p,'a',sid,0)==[i/12 for i in range(36)]
assert e.camera(c,2,sid)['lens']==32
print(json.dumps([e.camera(c,t)['lens'] for t in [0,2.5,3,4]]))`],{input:JSON.stringify(p),encoding:'utf8'});
  assert.equal(r.status,0,r.stderr);assert.deepEqual(JSON.parse(r.stdout),lenses);
 }
 assert.equal(JSON.stringify([a,b]),paths);
});

test('adjacent paths merge without changing the turn or allowing configured shots and actions',()=>{
 const {p,a,b,c}=fixture(),[left,right]=a.segments.map(s=>s.id);
 const samples=[.2,1.7,2.3,3.7].map(t=>new Evaluator(p).pose(a,t));
 assert.throws(()=>mergePaths(p,a,left,b.segments[0].id));
 a.segments[1].motion={name:'bound'};assert.throws(()=>mergePaths(p,a,left,right));delete a.segments[1].motion;
 configureShot(p,c,a,right,'FREE');assert.throws(()=>mergePaths(p,a,right,left));delete c.shots[right];
 const sid=mergePaths(p,a,right,left);
 assert.deepEqual(units(a)[0].members,[left,right]);assert.equal(units(a).length,1);
 assert.deepEqual([.2,1.7,2.3,3.7].map(t=>new Evaluator(p).pose(a,t)),samples);
 configureShot(p,c,a,sid,'FREE');assert.equal(currentShot(p).unit.endTime,4);
});
test('top draft track shows base camera and clips delete only their matching motion interval',()=>{
 const {p,a,b,c}=fixture();
 const cfg=configureShot(p,c,b,b.segments[0].id,'FREE');cfg.motion='DIAGONAL';cfg.velocity=[5,0,0];
 c.videoTracks=[a.id,b.id];
 let ev=new Evaluator(p);
 assert.deepEqual(ev.camera(c,1).position,ev.base(c,1).position);
 assert.notDeepEqual(ev.camera(c,1,b.segments[0].id).position,ev.base(c,1).position);
 a.smooth=true;a.nodes[1].radius=.8;a.nodes[2].position=[2,2,0];a.nodes[1].easing='IN_OUT';
 const id=mergePaths(p,a,...a.segments.map(s=>s.id));
 a.segments[0].clipCuts=[.5,1.5];
 const times=[0,.25,1.5,1.75,2,2.75,4];
 const before=new SegmentMotion(a),positions=times.map(t=>before.at(t)[0]);
 deletePathRange(p,a,id,.5,1.5);
 assert.deepEqual(units(a).map(u=>[u.startTime,u.endTime]),[[0,.5],[1.5,4]]);
 const after=new SegmentMotion(a);
 times.forEach((t,i)=>assert(Math.hypot(...after.at(t)[0].map((v,j)=>v-positions[i][j]))<1e-7));
 assert.deepEqual(pathErrors(a,true),[]);
 assert.equal(shotAt(p,c,1).owner.id,b.id);
 const saved=JSON.parse(JSON.stringify(p));assert.deepEqual(units(saved.objects[0]),units(a));
 const python=spawnSync('python',['-B','-c',`import json,sys
from backend.model import validate
from backend.export_plan import clip_times
from backend.segments import Evaluator
p,times=json.load(sys.stdin)
assert not validate(p,True),validate(p,True)
ev=Evaluator(p);a,b,c=p['objects']
assert len(clip_times(p,a['id'],a['segments'][0]['id'],0))==6
assert ev.camera(c,.25)['position']==ev.base(c,.25)['position']
assert ev.camera(c,1)['position']!=ev.base(c,1)['position']
print(json.dumps([ev.pose(a,t)['position'] for t in times]))`],{input:JSON.stringify([p,times]),encoding:'utf8'});
 assert.equal(python.status,0,python.stderr);
 JSON.parse(python.stdout).forEach((v,i)=>assert(Math.hypot(...v.map((x,j)=>x-positions[i][j]))<1e-7));
});