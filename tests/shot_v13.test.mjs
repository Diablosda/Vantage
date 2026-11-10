import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {migrate,newShot,edges,Evaluator,syncOrbit,inheritShot,convertShot,cameraQuaternion} from '../web/segments.js';
import {numberInput,orbitParameters,orbitPosition,validCameraState} from '../web/camera_state.js';
const close=(a,b)=>Array.isArray(a)?a.forEach((v,i)=>close(v,b[i])):assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);
export function fixture(){
 const obj=(id,role)=>({id,name:id,role,position:[0,0,0],rotation:[0,0,0],scale:[1,1,1],parts:[],nodes:[],angles:[],lenses:[],rolls:[],orientation:'FIXED'});
 const o=obj('actor','PROP');o.nodes=[[0,0,0],[2,0,0],[4,1,0]].map((position,i)=>({position,time:i*2,dwell:0,radius:.5}));
 o.parts=[{shape:'BOX',matrix:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}];
 const c=obj('camera','CAMERA');Object.assign(c,{position:[6,-8,5],viewMode:'LOCK',target:'target',lens:50,shots:{}});
 const target=obj('target','TARGET');Object.assign(target,{follow:o.id,offset:[0,0,1]});
 const p=migrate({version:2,name:'V1.3 回归',objects:[o,c,target],activeCamera:c.id,settings:{duration:4,fps:12,width:192,height:144,grid:.5,snap:false}}),ss=edges(o);
 for(const s of ss)c.shots[s.id]=newShot(p,c,o,s.id);
 return {p,o,c,ss,a:c.shots[ss[0].id],b:c.shots[ss[1].id]};
}
test('T01 T03 invalid numbers do not enter camera state; lens does not move camera',()=>{
 for(const raw of ['', ' ', 'abc','1e999',NaN,Infinity,undefined,null])assert.throws(()=>numberInput(raw));
 const {p,c,a}=fixture(),before=[...a.start.position];
 for(const lens of [1,6,65,1000,50]){a.lens=lens;const state=new Evaluator(p).camera(c,0);close(state.position,before);assert.ok(cameraQuaternion(validCameraState(state)).every(Number.isFinite));}
 a.lens=0;assert.throws(()=>new Evaluator(p).camera(c,0));
});
test('T04–T07 new segments and snapshot inheritance remain independent both ways',()=>{
 const {p,o,c,ss,a,b}=fixture();Object.assign(a,{motion:'DIAGONAL',velocity:[2,3,4],lens:65});
 assert.equal(b.inherit,false);assert.equal(b.motion,'TRANSLATE');assert.equal(b.lens,50);
 const frozen=structuredClone(b);for(let i=0;i<20;i++){new Evaluator(p).camera(c,i%2?0:2);a.start.position[0]++;}assert.deepEqual(b,frozen);
 const snapshot=inheritShot(p,c,o,ss[1].id),end=new Evaluator(p).camera(c,2,ss[0].id);close(snapshot.start.position,end.position);
 snapshot.focusLocal[0]=42;snapshot.velocity[0]=9;assert.equal(a.focusLocal[0],0);assert.equal(a.velocity[0],2);
 const copied=structuredClone(snapshot);a.start.position[2]=200;a.lens=25;assert.deepEqual(snapshot,copied);
});
test('T08–T12 spherical controls preserve the specified coordinates and last operation',()=>{
 const focus=[2,3,4];let position=[5,7,16],p=orbitParameters(position,focus);close(p.radius,5);close(p.dz,12);
 position=orbitPosition(position,focus,'azimuth',360);close(position,[7,3,16]);
 position=orbitPosition(position,focus,'radius',10);close(position,[12,3,16]);
 position=orbitPosition(position,focus,'elevation',-45);close(position,[12,3,-6]);
 position=[-4,8,12];position=orbitPosition(position,focus,'radius',2);p=orbitParameters(position,focus);close(p.radius,2);close(p.dz,8);
 assert.throws(()=>orbitPosition(position,focus,'radius',-1));assert.throws(()=>orbitPosition(position,focus,'elevation',90));
});
test('T13–T15 focus editing, pole and coincident states preserve real positions',()=>{
 const {p,c,a}=fixture();a.motion='ORBIT';
 for(const position of [[0,0,8],[0,0,-8],[0,0,1],[1e-9,0,8]]){
  a.start.position=position;const polar=syncOrbit(p,a,0);assert.ok(polar.polar);close(new Evaluator(p).camera(c,0).position,position);
  assert.ok(cameraQuaternion(new Evaluator(p).camera(c,0)).every(Number.isFinite));
  const next=orbitPosition(position,[0,0,1],'azimuth',65,28);close(orbitParameters(next,[0,0,1]).radius,.001);close(next[2],position[2]);
 }
 a.start.position=[3,-4,7];a.focusLocal=[2,1,5];syncOrbit(p,a,0);close(new Evaluator(p).camera(c,0).position,[3,-4,7]);
});
test('T16–T19 modes, trajectory and JS/Python roundtrip match at every sampled time',()=>{
 const {p,c,a,b,ss}=fixture();Object.assign(b,{motion:'ORBIT',orbitAngle:90,direction:-1,start:{...b.start,position:[3,5,8]}});
 for(const motion of ['ORBIT','DIAGONAL','TRANSLATE','DOLLY'])for(const orientation of ['LOCK','FREE']){
  Object.assign(a,{motion,orientation,orbitAngle:90,speed:.1,velocity:[.1,-.2,.3]});
  for(const position of [[3,-4,7],[0,0,8],[0,0,1]]){
   if(motion==='DOLLY'&&position[2]===1)continue;
   a.start.position=position;syncOrbit(p,a,0);const times=[0,.1,1,1.999,2,3,4],ev=new Evaluator(p),expected=times.map(t=>{const state=ev.camera(c,t);return [state.position,cameraQuaternion(state)];});close(expected[0][0],position);
   if(motion==='ORBIT'){const end=ev.camera(c,2,ss[0].id);close(end.position.map((v,i)=>v-end.focus[i]),[-position[1],position[0],position[2]-1]);}
   const r=spawnSync('python',['-c',"import sys,json;sys.path.insert(0,sys.argv[1]);from backend.segments import Evaluator,camera_quaternion;from backend.model import validate;p=json.load(sys.stdin);assert not validate(p['project']),validate(p['project']);e=Evaluator(p['project']);print(json.dumps([[s['position'],camera_quaternion(s)] for t in p['times'] for s in [e.camera(e.objects['camera'],t)]]))",fileURLToPath(new URL('..',import.meta.url))],{input:JSON.stringify({project:p,times}),encoding:'utf8'});
   assert.equal(r.status,0,r.stderr);JSON.parse(r.stdout).forEach((v,i)=>{close(v[0],expected[i][0]);close(Math.abs(v[1].reduce((sum,x,j)=>sum+x*expected[i][1][j],0)),1);});
  }
 }
});
test('legacy conversion is explicit and snapshots inherited start before changing rules',()=>{
 const {p,o,c,a,b,ss}=fixture();delete a.controlVersion;delete b.controlVersion;a.speed=2;b.inherit=true;
 const before=new Evaluator(p).camera(c,2).position;const loaded=migrate(JSON.parse(JSON.stringify(p)));assert.equal(loaded.objects[1].shots[ss[1].id].controlVersion,undefined);
 convertShot(p,c,o,ss[1].id);close(b.start.position,before);assert.equal(b.inherit,false);a.speed=10;close(new Evaluator(p).camera(c,2).position,before);
});
