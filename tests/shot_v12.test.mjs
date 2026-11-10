import {legacyShot as newShot} from './legacy_fixture.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import * as THREE from '../web/vendor/three/build/three.module.js';
import {migrate,edges,Evaluator,cameraQuaternion,captureStart,splitSegment} from '../web/segments.js';
const close=(a,b)=>{if(Array.isArray(a)){assert.equal(a.length,b.length);a.forEach((v,i)=>close(v,b[i]));}else assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);};
const rotationClose=(a,b)=>assert.ok(Math.abs(Math.abs(a.reduce((v,x,i)=>v+x*b[i],0))-1)<1e-6);
const rotate=(v,q)=>new THREE.Vector3(...v).applyQuaternion(new THREE.Quaternion(...q)).toArray();
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
function setup(){
 const obj=(id,role)=>({id,name:id,role,position:[0,0,0],rotation:[0,0,0],scale:[1,1,1],nodes:[],parts:[],orientation:'FIXED'});
 const o=obj('actor','PROP');o.nodes=[[0,0,0],[2,1,1],[1,3,2]].map((position,i)=>({position,time:i*2,dwell:0}));
 const c=obj('camera','CAMERA');Object.assign(c,{position:[0,-6,2],target:'target',viewMode:'LOCK',lens:50,shots:{}});
 const target=obj('target','TARGET');Object.assign(target,{follow:o.id,offset:[0,0,2]});
 const p=migrate({version:2,objects:[o,c,target],activeCamera:c.id,settings:{fps:24,duration:4,width:192,height:144,grid:.5}}),ss=edges(o);
 c.shots[ss[0].id]=newShot(p,c,o,ss[0].id);return {p,o,c,ss,cfg:c.shots[ss[0].id]};
}
test('V1.2 diagonal axes retain independent signed speeds over entire interval',()=>{
 const {p,c,cfg}=setup();Object.assign(cfg,{motion:'DIAGONAL',velocity:[1,-2,.5]});const ev=new Evaluator(p),a=ev.camera(c,0);
 for(const t of [0,.25,1,1.99,2]){const b=ev.camera(c,t,edges(p.objects[0])[0].id);close(sub(sub(b.position,a.position),sub(b.focus,a.focus)),cfg.velocity.map(v=>v*t));}
});
test('V1.2 dolly uses initial three-dimensional sight while focus translates and turns',()=>{
 for(const direction of [-1,1]){const {p,o,c,cfg,ss}=setup();o.orientation='PATH';cfg.focusLocal=[.5,.5,2];cfg.start.position=[4,-6,5];Object.assign(cfg,{motion:'DOLLY',speed:.7,direction});
 const ev=new Evaluator(p),a=ev.camera(c,0),sight=sub(a.focus,a.position),length=Math.hypot(...sight);
 for(const t of [.2,1,2]){const b=ev.camera(c,t,ss[0].id);close(sub(sub(b.position,a.position),sub(b.focus,a.focus)),sight.map(v=>v/length*.7*direction*t));}}
});
test('V1.2 signed pan, tilt and roll are actual rotations, including full turns',()=>{
 for(const sign of [-1,1])for(const axis of [0,1,2]){
  const {p,c,cfg,ss}=setup();cfg.orientation='FREE';cfg.rotationDelta=[0,0,0];cfg.rotationDelta[axis]=sign*Math.PI/2;
  const ev=new Evaluator(p),state=ev.camera(c,2,ss[0].id),q=cameraQuaternion(state);
  if(axis===0)close(rotate([0,0,-1],q),[-sign,0,0]);
  if(axis===1)close(rotate([0,0,-1],q),[0,0,sign]);
  if(axis===2){close(rotate([0,0,-1],q),[0,1,0]);close(rotate([1,0,0],q),[0,0,sign]);}
  cfg.rotationDelta[axis]=sign*2*Math.PI;const full=new Evaluator(p);rotationClose(cameraQuaternion(full.camera(c,0)),cameraQuaternion(full.camera(c,2,ss[0].id)));
  assert.ok(Math.abs(cameraQuaternion(full.camera(c,1)).reduce((sum,x,i)=>sum+x*cfg.start.quaternion[i],0))<1e-6);
 }
});
test('V1.2 free orientation is independent of moving focus; translation and combined rotation share progress',()=>{
 const {p,o,c,cfg,ss}=setup();cfg.orientation='FREE';Object.assign(cfg,{motion:'DIAGONAL',velocity:[.4,0,-.2],rotationDelta:[.8,.3,-.5]});
 const ev=new Evaluator(p),state=ev.camera(c,1);const expected=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),.4).multiply(new THREE.Quaternion(...cfg.start.quaternion)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),.15)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),-.25));rotationClose(cameraQuaternion(state),expected.toArray());
 const before=cameraQuaternion(state);o.nodes[1].position=[20,30,40];rotationClose(cameraQuaternion(new Evaluator(p).camera(c,1)),before);
 cfg.velocity=[0,0,0];cfg.rotationDelta=[0,0,0];const zero=new Evaluator(p);rotationClose(cameraQuaternion(zero.camera(c,0)),cameraQuaternion(zero.camera(c,2,ss[0].id)));
});
test('V1.2 target lock ignores pan and tilt but allows roll, including orbit',()=>{
 for(const motion of ['TRANSLATE','ORBIT']){const {p,c,cfg}=setup();if(motion==='ORBIT')Object.assign(cfg,{motion,tilt:0,radius:6});
 cfg.rotationDelta=[Math.PI,.5,.6];const state=new Evaluator(p).camera(c,.8);const direction=new THREE.Vector3(...sub(state.focus,state.position)).normalize().toArray();close(rotate([0,0,-1],cameraQuaternion(state)),direction);
 const expected=cameraQuaternion(state);cfg.rotationDelta=[0,0,.6];rotationClose(cameraQuaternion(new Evaluator(p).camera(c,.8)),expected);}
});
test('V1.2 inherited orientation remains continuous; unlocking and splitting preserve complete state',()=>{
 const {p,o,c,cfg,ss}=setup();Object.assign(cfg,{orientation:'FREE',motion:'DIAGONAL',velocity:[.3,.1,.2],rotationDelta:[.6,.4,.3]});
 c.shots[ss[1].id]=newShot(p,c,o,ss[1].id);const next=c.shots[ss[1].id];assert.deepEqual(next.rotationDelta,cfg.rotationDelta);assert.deepEqual(next.velocity,cfg.velocity);
 let ev=new Evaluator(p),end=ev.camera(c,2,ss[0].id);rotationClose(cameraQuaternion(ev.camera(c,2)),cameraQuaternion(end));close(ev.camera(c,2).position,end.position);
 cfg.rotationDelta[0]=1.4;ev=new Evaluator(p);rotationClose(cameraQuaternion(ev.camera(c,2)),cameraQuaternion(ev.camera(c,2,ss[0].id)));
 next.start=captureStart(ev.previous(c,o,1));next.inherit=false;const frozen=structuredClone(next.start);cfg.rotationDelta[0]=-.8;rotationClose(cameraQuaternion(new Evaluator(p).camera(c,2)),frozen.quaternion);
 next.start.quaternion=[0,0,0,1];rotationClose(cameraQuaternion(new Evaluator(p).camera(c,2)),[0,0,0,1]);
 splitSegment(p,o,ss[0].id);const a=edges(o)[0],b=edges(o)[1];ev=new Evaluator(p);rotationClose(c.shots[b.id].start.quaternion,cameraQuaternion(ev.camera(c,a.endTime,a.id)));assert.deepEqual(c.shots[a.id].rotationDelta,cfg.rotationDelta);
});
test('V1.2 dolly crossing target fails before playing, legacy shots default to locked orientation',()=>{
 const {p,c,cfg,ss}=setup();Object.assign(cfg,{motion:'DOLLY',speed:3,direction:1});assert.throws(()=>new Evaluator(p).camera(c,0),/推进/);
 cfg.orientation='FREE';assert.doesNotThrow(()=>new Evaluator(p).camera(c,2,ss[0].id));delete cfg.orientation;cfg.speed=0;delete cfg.rotationDelta;delete cfg.velocity;delete cfg.start.quaternion;assert.ok(cameraQuaternion(new Evaluator(p).camera(c,1)).every(Number.isFinite));
});
test('V1.2 web/Python match position and optical orientation for all combinations, hard cuts and roundtrip',()=>{
 for(const motion of ['TRANSLATE','DIAGONAL','DOLLY','ORBIT'])for(const orientation of ['LOCK','FREE']){
 const {p,o,c,cfg,ss}=setup();Object.assign(cfg,{motion,orientation,speed:.7,direction:-1,velocity:[.2,-.7,.4],rotationDelta:[.8,-.4,.6],radius:6,tilt:0});c.shots[ss[1].id]=newShot(p,c,o,ss[1].id);
 const times=[0,.1,.5,1,1.9999,2,2.1,3,4,1],ev=new Evaluator(p),expected=times.map(t=>{const state=ev.camera(c,t);return {position:state.position,rotation:cameraQuaternion(state)};});
 const r=spawnSync('python',['-c',"import sys,json;sys.path.insert(0,sys.argv[1]);from backend.segments import Evaluator,camera_quaternion;p=json.load(sys.stdin);e=Evaluator(p['project']);out=[]\nfor t in p['times']:\n s=e.camera(e.objects['camera'],t);out.append(dict(position=s['position'],rotation=camera_quaternion(s)))\nprint(json.dumps(out))",fileURLToPath(new URL('..',import.meta.url))],{input:JSON.stringify({project:p,times}),encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);JSON.parse(r.stdout).forEach((v,i)=>{close(v.position,expected[i].position);rotationClose(v.rotation,expected[i].rotation);});
 }
});

test('free orbit starts at any dragged position and matches Python throughout the full circle',()=>{
 for(const position of [[3,-4,7],[0,0,8],[-6,2,-1]])for(const tilt of [0,45,90,180]){
  const {p,c,cfg,ss}=setup();Object.assign(cfg,{motion:'ORBIT',orbitFree:true,tilt,start:{...cfg.start,position},orientation:'LOCK'});const ev=new Evaluator(p),times=[0,.25,1,1.75,2],states=times.map(t=>ev.camera(c,t,ss[0].id)),radius=Math.hypot(...sub(position,states[0].focus));close(states[0].position,position);states.forEach(state=>close(Math.hypot(...sub(state.position,state.focus)),radius));close(sub(states[4].position,states[4].focus),sub(states[0].position,states[0].focus));
  const r=spawnSync('python',['-c',"import sys,json;sys.path.insert(0,sys.argv[1]);from backend.segments import Evaluator,camera_quaternion;p=json.load(sys.stdin);e=Evaluator(p['project']);print(json.dumps([dict(position=(s:=e.camera(e.objects['camera'],t,p['sid']))['position'],rotation=camera_quaternion(s)) for t in p['times']]))",fileURLToPath(new URL('..',import.meta.url))],{input:JSON.stringify({project:p,times,sid:ss[0].id}),encoding:'utf8'});assert.equal(r.status,0,r.stderr);JSON.parse(r.stdout).forEach((state,i)=>{close(state.position,states[i].position);rotationClose(state.rotation,cameraQuaternion(states[i]));});
 }
});
