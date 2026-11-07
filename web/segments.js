// Portable timed path graph and shot evaluator. Mirrored by backend/segments.py.
import {Arc,add,sub,mul,distance,unit,length,ease,keyValue,keyInterval} from './math.js';
import {orbitParameters,validCameraState,POSITION_EPS} from './camera_state.js';
import * as THREE from './vendor/three/build/three.module.js';
const EPS=1e-7,TAU=2*Math.PI;
const uid=()=>crypto.randomUUID();
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const qrot=r=>new THREE.Quaternion().setFromEuler(new THREE.Euler(...r,'ZYX'));
const rotate=(v,q)=>new THREE.Vector3(...v).applyQuaternion(q).toArray();
const bez=(a,b,c,t)=>add(add(mul(a,(1-t)**2),mul(b,2*t*(1-t))),mul(c,t*t));
export function migrate(project){for(const o of project.objects){o.nodes??=[];o.nodes.forEach((n,i)=>n.id??=`${o.id}-point-${i}`);if(!o.segments)o.segments=o.nodes.slice(1).map((n,i)=>({id:`${o.id}-segment-${i}`,start:o.nodes[i].id,end:n.id}));syncSegments(o);}return project;}
export function syncSegments(o){const ns=new Map(o.nodes.map(n=>[n.id,n]));for(const s of o.segments||[]){const a=ns.get(s.start),b=ns.get(s.end);if(a&&b){s.startTime=a.time+(a.dwell||0);s.endTime=b.time;}}}
export function edges(o){const ns=new Map(o.nodes.map(n=>[n.id,n]));return (o.segments||[]).map(s=>({...s,a:ns.get(s.start),b:ns.get(s.end)})).filter(s=>s.a&&s.b).sort((a,b)=>a.startTime-b.startTime);}
export function pathErrors(o,full=false){const errors=[],ns=o.nodes||[],ss=edges(o);if(new Set(ns.map(n=>n.id)).size!==ns.length)errors.push('控制点标识重复');if(new Set((o.segments||[]).map(s=>s.id)).size!==(o.segments||[]).length)errors.push('线段标识重复');if(ss.length!==(o.segments||[]).length)errors.push('线段端点不存在');for(const n of ns)if(![...n.position,n.time,n.dwell||0,n.radius??.5].every(Number.isFinite)||n.time<0||(n.dwell||0)<0||(n.radius??.5)<0)errors.push('控制点数值无效');for(let i=0;i<ss.length;i++){const s=ss[i];if(s.endTime-s.startTime<=EPS)errors.push('线段时长必须大于零');if(distance(s.a.position,s.b.position)<=EPS)errors.push('线段长度必须大于零');if(i&&s.startTime<ss[i-1].endTime-EPS)errors.push('线段时间重叠');if(full&&i&&s.start!==ss[i-1].end)errors.push('路径不连续：请修复连接或单独预演线段');}return [...new Set(errors)];}
export class SegmentMotion{
 constructor(o){this.object=o;this.segments=edges(o);this.arcs=[];const corners=new Map();if(o.smooth)for(let i=1;i<this.segments.length;i++){const prev=this.segments[i-1],s=this.segments[i],n=s.a;if(prev.end!==s.start||n.exact||n.dwell)continue;const a=prev.a.position,b=n.position,c=s.b.position,u=unit(sub(a,b)),v=unit(sub(c,b)),r=Math.min(n.radius??.5,distance(a,b)*.49,distance(b,c)*.49);if(r>EPS&&Math.abs(dot(u,v))<.99999)corners.set(n.id,[add(b,mul(u,r)),b,add(b,mul(v,r))]);}
  for(const s of this.segments){const points=[];if(corners.has(s.start))for(let j=0;j<=64;j++)points.push(bez(...corners.get(s.start),.5+j/128));else points.push(s.a.position);if(corners.has(s.end))for(let j=0;j<=64;j++)points.push(bez(...corners.get(s.end),j/128));else points.push(s.b.position);this.arcs.push(new Arc(points));}
 }
 at(t,only=null){let last=null;for(let i=0;i<this.segments.length;i++){const s=this.segments[i],arc=this.arcs[i];if(only&&s.id!==only)continue;if(t<s.startTime&&last)return last;const f=ease((t-s.startTime)/Math.max(EPS,s.endTime-s.startTime),s.b.easing);const p=arc.at(f)[0],tangent=unit(sub(arc.at(Math.min(1,f+.001))[0],arc.at(Math.max(0,f-.001))[0]));last=[p,tangent];if(t<s.endTime)return last;}return last||[this.object.nodes[0]?.position||this.object.position,[0,0,0]];}
}
export function retime(o){syncSegments(o);if(o.timing!=='SPEED'||!o.segments?.length)return;const motion=new SegmentMotion(o),ss=motion.segments;for(let i=0;i<ss.length;i++){const s=ss[i];s.b.time=s.a.time+(s.a.dwell||0)+motion.arcs[i].total/Math.max(.001,o.speed||1);}syncSegments(o);}
export function appendPoint(o,position){if(!o.nodes.length)o.nodes.push({id:uid(),position:[...o.position],time:0,dwell:0,radius:.5,easing:'LINEAR'});const prev=o.nodes.at(-1);if(distance(prev.position,position)<EPS)throw Error('新控制点不能与末点重合');const n={id:uid(),position:[...position],time:prev.time+(prev.dwell||0)+distance(prev.position,position)/(o.speed||1),dwell:0,radius:.5,easing:'LINEAR'};o.nodes.push(n);o.segments.push({id:uid(),start:prev.id,end:n.id});syncSegments(o);retime(o);return n;}
export function splitSegment(project,o,sid){const s=edges(o).find(s=>s.id===sid);if(!s)throw Error('请选择有效线段');const n={id:uid(),position:mul(add(s.a.position,s.b.position),.5),time:(s.startTime+s.endTime)/2,dwell:0,radius:s.b.radius??.5,exact:false,easing:s.b.easing||'LINEAR'};o.nodes.splice(o.nodes.indexOf(s.b),0,n);const first={id:uid(),start:s.start,end:n.id,...(s.motion?{motion:structuredClone(s.motion)}:{})},second={id:uid(),start:n.id,end:s.end,...(s.motion?{motion:structuredClone(s.motion)}:{})};o.segments.splice(o.segments.findIndex(x=>x.id===sid),1,first,second);for(const c of project.objects){if(c.shots?.[sid]){c.shots[first.id]=structuredClone(c.shots[sid]);c.shots[second.id]=structuredClone(c.shots[sid]);delete c.shots[sid];}}syncSegments(o);retime(o);for(const c of project.objects){const cfg=c.shots?.[second.id];if(cfg&&!cfg.inherit){try{const ss=edges(o),ev=new Evaluator(project),end=ev.shot(c,o,ss.findIndex(s=>s.id===first.id),ss.find(s=>s.id===first.id).endTime);cfg.start=captureStart(end);}catch{ /* Preserve conflicting inputs for explicit user correction. */ }}}return first.id;}
function removeSegments(project,o,ids,points=[]){
 const removed=new Set(ids),affected=new Set(points);
 for(const s of o.segments)if(removed.has(s.id)){affected.add(s.start);affected.add(s.end);}
 o.segments=o.segments.filter(s=>!removed.has(s.id));
 const used=new Set(o.segments.flatMap(s=>[s.start,s.end]));
 o.nodes=o.nodes.filter(n=>!affected.has(n.id)||used.has(n.id));
 for(const c of project.objects)for(const sid of removed)if(c.shots)delete c.shots[sid];
 syncSegments(o);
}
export function deleteSegment(project,o,sid){removeSegments(project,o,[sid]);}
export function deletePoint(project,o,nid){removeSegments(project,o,o.segments.filter(s=>s.start===nid||s.end===nid).map(s=>s.id),[nid]);}
export function clearPath(project,o){
 removeSegments(project,o,o.segments.map(s=>s.id),o.nodes.map(n=>n.id));
 // Also discard stale configurations owned by this path, including imported projects.
 for(const c of project.objects)for(const [sid,cfg] of Object.entries(c.shots||{}))if(cfg.owner===o.id||(cfg.mode==='TRACK'&&cfg.focusTarget===o.id))delete c.shots[sid];
}
export function followOwner(project,c){const t=project.objects.find(o=>o.id===c?.target);return c?.viewMode==='LOCK'?project.objects.find(o=>o.id===t?.follow):null;}
export class Evaluator{
 constructor(p){this.p=p;this.objects=new Map(p.objects.map(o=>[o.id,o]));this.motions=new Map(p.objects.filter(o=>o.segments?.length).map(o=>[o.id,new SegmentMotion(o)]));}
 pose(o,t,only=null){let [position,tangent]=this.motions.get(o.id)?.at(t,only)||[o.position,[0,0,0]],q=qrot(o.rotation);if(o.orientation==='PATH'&&length(tangent)>EPS)q=qrot([o.lockZ||['ACTOR','PROP'].includes(o.role)?0:Math.asin(tangent[2]),0,Math.atan2(-tangent[0],tangent[1])+(o.frontAxis==='-Y'?Math.PI:0)]);else if(o.orientation==='MANUAL'&&o.angles?.length){const [a,b,f]=keyInterval(o.angles,t);q=qrot(a.rotation).slerp(qrot(b.rotation),f);}if(o.follow){const target=this.objects.get(o.follow);if(target)position=this.focus(target,o.offset||[0,0,0],t,only);}return {position:[...position],quaternion:q.toArray(),scale:o.scale};}
 focus(o,local,t,only=null){const pose=this.pose(o,t,only);return add(pose.position,rotate(local.map((v,i)=>v*o.scale[i]),new THREE.Quaternion(...pose.quaternion)));}
 base(c,t){const pose=this.pose(c,t),target=this.objects.get(c.target);return {...pose,focus:c.viewMode==='LOCK'&&target?this.pose(target,t).position:null,lens:keyValue(c.lenses||[],t,c.lens),roll:c.rollEnabled?keyValue(c.rolls||[],t,c.roll||0):0,up:[0,0,1]};}
 previous(c,owner,index){const ss=edges(owner);return index>0?this.shot(c,owner,index-1,ss[index-1].endTime):this.base(c,ss[0]?.startTime||0);}
 shot(c,owner,index,t,unitOverride=null){
  const s=unitOverride||edges(owner)[index],cfg=c.shots?.[s.id];if(!cfg)return this.base(c,t);
  const target=this.objects.get(cfg.focusTarget);if(!target&&cfg.mode!=='FREE')throw Error('镜头焦点对象不存在');
  const inherited=cfg.controlVersion!==3&&cfg.inherit&&index>0,start=inherited?this.previous(c,owner,index):cfg.start;
  const duration=s.endTime-s.startTime,dt=Math.max(0,Math.min(t-s.startTime,duration)),progress=dt/duration;
  const f0=cfg.mode==='FREE'?cfg.focusWorld:this.focus(target,cfg.focusLocal,s.startTime),focus=cfg.mode==='FREE'?f0:this.focus(target,cfg.focusLocal,s.startTime+dt),free=cfg.orientation==='FREE';
  let position,up=[0,0,1];
  if(cfg.motion==='ORBIT'){
   const theta=cfg.tilt*Math.PI/180,offset=sub(start.position,f0);let u,v,normal,radius;
   if(cfg.controlVersion===3){
    const angle=cfg.direction*(cfg.orbitAngle??360)*Math.PI/180*progress,co=Math.cos(angle),si=Math.sin(angle);
    position=add(focus,[offset[0]*co-offset[1]*si,offset[0]*si+offset[1]*co,offset[2]]);
   }else if(cfg.orbitFree){
    radius=length(offset);if(radius<1e-5)throw Error('环绕起始机位不能与焦点重合');u=unit(offset);
    let reference=[0,0,1];if(Math.abs(dot(reference,u))>.999)reference=[0,1,0];
    const base=unit(sub(reference,mul(u,dot(reference,u))));
    normal=rotate(base,new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...u),theta));v=cross(normal,u);
    const angle=cfg.direction*TAU*progress;position=add(focus,add(mul(u,radius*Math.cos(angle)),mul(v,radius*Math.sin(angle))));up=normal;
   }else{
    u=[1,0,0];v=[0,Math.cos(theta),Math.sin(theta)];normal=cross(u,v);radius=cfg.radius;
    if(Math.abs(dot(offset,normal))>1e-4||Math.abs(length(offset)-radius)>1e-4)throw Error('环绕起始机位与焦点、半径或倾角冲突：调整参数，或解除继承后设置起点');
    const phase=Math.atan2(dot(offset,v),dot(offset,u)),angle=phase+cfg.direction*TAU*progress;
    position=add(focus,add(mul(u,radius*Math.cos(angle)),mul(v,radius*Math.sin(angle))));up=normal;
   }
  }else{
   let velocity=[0,0,0];
   if(cfg.motion==='DIAGONAL')velocity=cfg.velocity||[0,0,0];
   else if(cfg.motion==='DOLLY'){
    const sight=sub(f0,start.position),dist=length(sight);
    if(dist<1e-5)throw Error('沿视线运动需要不同的起始机位与焦点');
    if(!free&&cfg.direction>0&&cfg.speed*duration>=dist-1e-5)throw Error('推进会到达或越过焦点：请降低速度或缩短线段时长');
    velocity=mul(unit(sight),cfg.direction*cfg.speed);
   }else velocity['XYZ'.indexOf(cfg.axis)]=cfg.direction*cfg.speed;
   position=add(add(start.position,sub(focus,f0)),mul(velocity,dt));
  }
  const delta=cfg.rotationDelta||[0,0,0],roll=inherited?(start.roll||0):(cfg.roll??start.roll??0);
  if(cfg.mode==='FREE'&&cfg.freeMotion?.segments?.length){const path=new SegmentMotion(cfg.freeMotion);position=add(position,sub(path.at(s.startTime+dt)[0],path.at(s.startTime)[0]));}
  const state={position,focus,up,lens:cfg.lensEnd!==undefined?cfg.lens+(cfg.lensEnd-cfg.lens)*progress:(cfg.lens??start.lens??c.lens),roll:roll+delta[2]*progress};
  if(free){
   const initial=inherited?cameraQuaternion(start):(start.quaternion||cameraQuaternion({position:start.position,focus:f0,up,roll}));
   // Pan about world vertical, then tilt about starting camera right, then roll about the resulting optical axis.
   state.cameraRotation=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),delta[0]*progress)
    .multiply(new THREE.Quaternion(...initial)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),delta[1]*progress))
    .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),delta[2]*progress)).normalize().toArray();
  }else if(distance(position,focus)<POSITION_EPS){state.cameraRotation=[...(start.quaternion||qrot(c.rotation).toArray())];state.warning='摄影机与焦点重合，暂时保留起始朝向；可继续移动机位';}
  if(cfg.mode==='FREE'&&cfg.freeMotion){const m=cfg.freeMotion;state.lens=keyValue(m.lenses||[],s.startTime+dt,state.lens);if(m.angles?.length){const [a,b,f]=keyInterval(m.angles,s.startTime+dt);state.cameraRotation=qrot(a.rotation).slerp(qrot(b.rotation),f).toArray();}}
  return validCameraState(state);
 }
 camera(c,t,only=null){if(this.p.shotFramework===2){const entry=shotAt(this.p,c,t,only);if(!entry)return this.base(c,t);return this.shot(c,entry.owner,0,t,entry.unit);}const owner=followOwner(this.p,c);if(!owner)return this.base(c,t);const ss=edges(owner);let index=only?ss.findIndex(s=>s.id===only):ss.findIndex((s,i)=>t>=s.startTime&&(t<s.endTime||(i===ss.length-1&&t<=s.endTime)));return index>=0?this.shot(c,owner,index,t):this.base(c,t);}
}
export function newShot(p,c,o,sid){
 const s=edges(o).find(s=>s.id===sid),ev=new Evaluator(p),target=p.objects.find(x=>x.id===c.target);
 // Explicit defaults use the base camera, never a previous segment or its live endpoint.
 const state=ev.base(c,s.startTime),start=captureStart(state),focusLocal=[...(target?.offset||[0,0,0])];
 const cfg={controlVersion:3,owner:o.id,focusTarget:o.id,focusLocal,motion:'TRANSLATE',orientation:'LOCK',velocity:[0,0,0],rotationDelta:[0,0,0],axis:'X',direction:1,speed:0,tilt:0,radius:0,orbitAngle:360,azimuth:0,lens:state.lens,roll:state.roll||0,inherit:false,start};
 syncOrbit(p,cfg,s.startTime);return cfg;
}
export function syncOrbit(p,cfg,time){
 if(cfg.controlVersion!==3)return;
 const ev=new Evaluator(p),target=ev.objects.get(cfg.focusTarget),focus=cfg.mode==='FREE'?cfg.focusWorld:ev.focus(target,cfg.focusLocal,time);
 const parameters=orbitParameters(cfg.start.position,focus,cfg.azimuth||0);
 cfg.azimuth=parameters.azimuth;cfg.radius=parameters.radius;return parameters;
}
export function convertShot(p,c,o,sid){
 const cfg=c.shots[sid],ss=edges(o),index=ss.findIndex(s=>s.id===sid),ev=new Evaluator(p);
 const start=cfg.inherit&&index>0?captureStart(ev.previous(c,o,index)):structuredClone(cfg.start);
 cfg.start=start;cfg.inherit=false;cfg.controlVersion=3;cfg.orbitAngle??=360;cfg.azimuth??=0;
 syncOrbit(p,cfg,ss[index].startTime);return cfg;
}
export function inheritShot(p,c,o,sid){
 const ss=edges(o),index=ss.findIndex(s=>s.id===sid);if(index<=0)throw Error('首段没有可继承的上一镜');
 const previous=c.shots?.[ss[index-1].id];if(!previous)throw Error('上一段尚未配置镜头');
 const state=new Evaluator(p).previous(c,o,index),copy=structuredClone(previous);
 Object.assign(copy,{start:captureStart(state),inherit:false,controlVersion:3,owner:o.id,orbitAngle:previous.orbitAngle??360,lens:state.lens,roll:state.roll||0});
 syncOrbit(p,copy,ss[index].startTime);c.shots[sid]=copy;return copy;
}
export function captureStart(state){return {position:[...state.position],quaternion:cameraQuaternion(state),lens:state.lens,roll:state.roll||0};}
export function cameraQuaternion(state){if(state.cameraRotation)return state.cameraRotation;if(!state.focus)return state.quaternion;if(distance(state.position,state.focus)<POSITION_EPS)return state.quaternion||[0,0,0,1];const z=unit(sub(state.position,state.focus));let x=unit(cross(state.up||[0,0,1],z));if(length(x)<EPS)x=unit(cross([0,1,0],z));const y=cross(z,x),m=new THREE.Matrix4().makeBasis(new THREE.Vector3(...x),new THREE.Vector3(...y),new THREE.Vector3(...z));return new THREE.Quaternion().setFromRotationMatrix(m).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),state.roll||0)).toArray();}

// Scene time units do not alter the path graph. Dwell units are derived, never stored as edges.
export function units(o){return [...edges(o),...(o.nodes||[]).filter(n=>n.dwell>0).map(n=>({id:n.id,kind:'DWELL',a:n,b:n,startTime:n.time,endTime:n.time+n.dwell}))].sort((a,b)=>a.startTime-b.startTime);}
export function shotEntries(p,cameraId=p.activeCamera){const result=[];for(const c of p.objects.filter(c=>c.id===cameraId))for(const [sid,cfg]of Object.entries(c.shots||{})){const owner=p.objects.find(o=>o.id===cfg.owner),unit=owner&&units(owner).find(u=>u.id===sid);if(unit)result.push({c,cfg,owner,unit});}return result.sort((a,b)=>a.unit.startTime-b.unit.startTime||a.unit.id.localeCompare(b.unit.id));}
export function shotAt(p,c,t,only=null){const entries=shotEntries(p,c.id);if(only)return entries.find(e=>e.unit.id===only)||null;return entries.find(e=>t>=e.unit.startTime&&t<e.unit.endTime)||(entries.at(-1)?.unit.endTime===t?entries.at(-1):null);}
export function currentShot(p){const entries=shotEntries(p);return entries.find(e=>e.unit.id===p.editShotId)||entries[0]||null;}
export function setDwell(o,n,value){if(!Number.isFinite(value)||value<0)throw Error('停留时间必须大于等于零');const delta=value-(n.dwell||0),index=o.nodes.indexOf(n);n.dwell=value;for(const next of o.nodes.slice(index+1))next.time+=delta;syncSegments(o);retime(o);}
export function setUnitDuration(o,sid,value){if(!Number.isFinite(value)||value<=0)throw Error('运动时长必须大于零');const s=edges(o).find(s=>s.id===sid);if(!s)throw Error('线段不存在');o.timing='TIME';const delta=value-(s.endTime-s.startTime);for(const n of o.nodes.slice(o.nodes.indexOf(s.b)))n.time+=delta;syncSegments(o);}
export function configureShot(p,c,o,sid,mode,inherit=false){
 const unit=units(o).find(s=>s.id===sid);if(!unit)throw Error('请选择线段或正数停留点');
 if(!['FREE','TRACK'].includes(mode))throw Error('请选择拍摄模式');
 const tracking=edges(o).length&&!pathErrors(o).length?o:p.objects.find(x=>['ACTOR','PROP'].includes(x.role)&&edges(x).length&&!pathErrors(x).length);if(mode==='TRACK'&&!tracking)throw Error('跟踪模式需要有效运动路径');
 const previous=currentShot(p),ev=new Evaluator(p);
 const state=inherit&&previous?ev.camera(previous.c,previous.unit.endTime,previous.unit.id):ev.base(c,0);
 const cfg=inherit&&previous?structuredClone(previous.cfg):{controlVersion:3,motion:'TRANSLATE',velocity:[0,0,0],rotationDelta:[0,0,0],axis:'X',direction:1,speed:0,tilt:0,radius:0,orbitAngle:360,azimuth:0};
 Object.assign(cfg,{owner:o.id,mode,focusTarget:tracking?.id||o.id,focusLocal:[0,0,0],focusWorld:[...(state.focus||add(state.position,rotate([0,0,-5],new THREE.Quaternion(...cameraQuaternion(state)))))],orientation:mode==='FREE'?'FREE':(inherit&&previous?.cfg.mode==='TRACK'?previous.cfg.orientation:'LOCK'),inherit:false,start:captureStart(state),lens:state.lens,roll:state.roll||0});
 // Across modes preserve the actual sight point in the new target's local coordinates.
 if(mode==='TRACK'&&inherit){const pose=ev.pose(tracking,unit.startTime),q=new THREE.Quaternion(...pose.quaternion).invert();cfg.focusLocal=rotate(sub(cfg.focusWorld,pose.position),q).map((v,i)=>v/tracking.scale[i]);}
 cfg.freeMotion??={id:c.id,position:[...cfg.start.position],rotation:[0,0,0],scale:[1,1,1],nodes:[],segments:[],angles:[],lenses:[],smooth:false,timing:'TIME'};
 syncOrbit(p,cfg,unit.startTime);
 c.shots??={};c.shots[sid]=cfg;p.editShotId=sid;p.shotFramework=2;
 return cfg;
}
export function pruneCurrentShot(p){if(p.shotFramework!==2)return;for(const c of p.objects)for(const [sid,cfg]of Object.entries(c.shots||{})){const owner=p.objects.find(o=>o.id===cfg.owner);if(!owner||!units(owner).some(u=>u.id===sid))delete c.shots[sid];}}

export function upgradeFramework(p,time=0){
 if(p.shotFramework===2)return p;
 const c=p.objects.find(o=>o.id===p.activeCamera),entries=[];
 for(const [sid,cfg]of Object.entries(c?.shots||{})){const owner=p.objects.find(o=>o.id===cfg.owner),unit=owner&&units(owner).find(u=>u.id===sid);if(unit)entries.push({sid,cfg,owner,unit});}
 const ev=new Evaluator(p),updates=entries.map(({cfg,owner,unit})=>({cfg,state:ev.shot(c,owner,edges(owner).findIndex(s=>s.id===unit.id),unit.startTime),owner,unit}));
 for(const {cfg,state,owner,unit}of updates){cfg.start=captureStart(state);cfg.inherit=false;cfg.mode='TRACK';cfg.focusWorld=[...(state.focus||ev.focus(owner,cfg.focusLocal,unit.startTime))];}
 p.editShotId=(entries.find(e=>time>=e.unit.startTime&&time<e.unit.endTime)||entries[0])?.sid;p.shotFramework=2;return p;
}

// Reuse the existing path/keyframe editor on the shared scene clock; data belongs to this shot.
export function editObject(p,o){const entry=currentShot(p);if(!o||entry?.c.id!==o.id||entry.cfg.mode!=='FREE')return o;const m=entry.cfg.freeMotion;if(!m)return o;const fields=new Set(['nodes','segments','angles','lenses','smooth','timing','speed','orientation']);return new Proxy(o,{get:(target,key)=>fields.has(key)?m[key]:target[key],set:(target,key,value)=>{if(fields.has(key))m[key]=value;else target[key]=value;return true;}});}
