import {gridLayout} from './grid_layout.js';
import {applyModelMaterialFallback} from './model_material.js';
import {validCameraState,finiteVector} from './camera_state.js';
import {Evaluator,SegmentMotion,editObject,currentShot,units,edges,cameraQuaternion,followOwner} from './segments.js';
import {controlPoint,controlScale} from './camera_control.js';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {TransformControls} from 'three/addons/controls/TransformControls.js';
import {Motion,keyInterval,keyValue,orthogonalize} from './math.js';

const vec=a=>new THREE.Vector3(...a);
const quat=a=>new THREE.Quaternion().setFromEuler(new THREE.Euler(...a,'ZYX'));
export const rotationOf=q=>{const e=new THREE.Euler().setFromQuaternion(q,'ZYX');return [e.x,e.y,e.z];};
export function lookRotation(position,target,roll=0){const m=new THREE.Matrix4().lookAt(vec(position),vec(target),new THREE.Vector3(0,0,1));const q=new THREE.Quaternion().setFromRotationMatrix(m);return q.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),roll));}

export function sceneGridMetrics(project,includeHidden=false){
 const total=new THREE.Box3(),temp=new THREE.Vector3(),objectBox=new THREE.Box3();let ground=0,largest=0;
 for(const o of project.objects){if((o.hidden&&!includeHidden)||o.role!=='ENV'||!o.parts?.length)continue;objectBox.makeEmpty();
  const world=new THREE.Matrix4().compose(vec(o.position),quat(o.rotation),vec(o.scale));
  for(const p of o.parts){const m=world.clone().multiply(new THREE.Matrix4().fromArray(p.matrix));if(p.shape==='MESH'){for(const v of p.vertices||[])objectBox.expandByPoint(temp.fromArray(v).applyMatrix4(m));}else for(const x of [-.5,.5])for(const y of [-.5,.5])for(const z of [-.5,.5])objectBox.expandByPoint(temp.set(x,y,z).applyMatrix4(m));}
  if(objectBox.isEmpty())continue;total.union(objectBox);const size=objectBox.getSize(new THREE.Vector3()),area=size.x*size.y;if(area>largest&&size.z<=Math.max(.75,Math.min(size.x,size.y)*.05)){largest=area;ground=objectBox.max.z;}
 }
 return {bounds:total.isEmpty()?null:{min:total.min.toArray(),max:total.max.toArray()},ground};
}

export class Viewport{
 constructor(container,preview,events){
  this.container=container;this.preview=preview;this.events=events;this.roots=new Map();this.motions=new Map();this.project=null;this.selected=null;this.nodeIndex=-1;this.view='TOP';this.tool='translate';this.editLayer='OBJECT';this.helpersOn=true;this.time=0;
  this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#131922');this.content=new THREE.Group();this.helpers=new THREE.Group();this.pathGroup=new THREE.Group();this.helpers.add(this.pathGroup);this.scene.add(this.content,this.helpers);
  this.scene.add(new THREE.HemisphereLight(0xeaf1ff,0x3e4248,2.6));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(4,-6,10);this.scene.add(light);const fill=new THREE.DirectionalLight(0xadc6e8,.8);fill.position.set(-5,2,3);this.scene.add(fill);
  this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));this.renderer.outputColorSpace=THREE.SRGBColorSpace;container.appendChild(this.renderer.domElement);
  this.renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();this.events.message?.('三维绘图连接已中断，正在等待浏览器恢复；这不是机位设置错误。');});this.renderer.domElement.addEventListener('webglcontextrestored',()=>this.events.message?.('三维绘图已恢复'));
  this.previewRenderer=new THREE.WebGLRenderer({antialias:true});this.previewRenderer.setPixelRatio(Math.min(devicePixelRatio,2));this.previewRenderer.outputColorSpace=THREE.SRGBColorSpace;preview.prepend(this.previewRenderer.domElement);this.previewRenderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();this.events.message?.('摄影机预览绘图连接中断，工作区仍可编辑；等待浏览器恢复。',true);});
  this.ortho=new THREE.OrthographicCamera(-8,8,6,-6,.01,2000);this.perspective=new THREE.PerspectiveCamera(45,1,.01,2000);this.ortho.up.set(0,1,0);this.perspective.up.set(0,0,1);this.camera=this.ortho;this.perspective.position.set(8,-11,9);this.perspective.lookAt(0,0,0);
  this.orbit=new OrbitControls(this.camera,this.renderer.domElement);this.orbit.enableDamping=false;this.orbit.screenSpacePanning=true;this.orbit.mouseButtons={LEFT:THREE.MOUSE.PAN,MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE.ROTATE};
  this.control=new TransformControls(this.camera,this.renderer.domElement);this.control.setSize(.8);this.scene.add(this.control.getHelper());this.handle=new THREE.Object3D();this.scene.add(this.handle);
  this.control.addEventListener('dragging-changed',e=>{this.orbit.enabled=!e.value;this.dragging=e.value;});
  this.control.addEventListener('mouseDown',()=>this.events.start?.());
  this.control.addEventListener('objectChange',()=>{if(!this.control.object)return;this.events.transform?.({position:this.control.object.position.toArray(),rotation:rotationOf(this.control.object.quaternion),node:this.nodeIndex});});
  this.control.addEventListener('mouseUp',()=>this.events.end?.());
  this.ray=new THREE.Raycaster();this.mouse=new THREE.Vector2();this.renderer.domElement.addEventListener('pointerdown',e=>{this.pointer=[e.clientX,e.clientY];});
  this.renderer.domElement.addEventListener('pointerdown',e=>this.targetDragStart(e),true);
  this.renderer.domElement.addEventListener('pointermove',e=>this.targetDragMove(e),true);
  this.renderer.domElement.addEventListener('pointerup',e=>this.targetDragEnd(e),true);
  this.renderer.domElement.addEventListener('pointercancel',e=>this.targetDragEnd(e),true);
  this.renderer.domElement.addEventListener('pointerup',e=>this.pointerUp(e));this.renderer.domElement.addEventListener('contextmenu',e=>this.contextMenu(e));
  new ResizeObserver(()=>this.resize()).observe(container);new ResizeObserver(()=>this.resize()).observe(preview);this.setView('TOP');
 }
 disposeTree(group){group.traverse(o=>{o.geometry?.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();}});group.clear();}
 setProject(project){
  const structureKey=JSON.stringify(project.objects.map(o=>[o.id,o.role,o.modelSource,o.locatorColor,o.role==='ENV'?[o.position,o.rotation,o.scale,o.hidden]:null,(o.segments||[]).map(s=>[s.id,s.motion?.name]),(o.parts||[]).map(p=>[p.shape,p.topRatio,p.matrix,p.vertices?.length,p.triangles?.length])]).concat([project.settings.grid]));
  if(this.structureKey===structureKey){this.project=project;this.evaluator=new Evaluator(project);this.refreshPaths();this.update(this.time);this.resize();return;}
  this.structureKey=structureKey;this.project=project;this.evaluator=new Evaluator(project);this.control.detach();this.disposeTree(this.content);this.roots.clear();this.motions.clear();this.disposeTree(this.helpers);this.pathGroup=new THREE.Group();this.helpers.add(this.pathGroup);
  const metrics=sceneGridMetrics(project),layout=gridLayout(metrics.bounds,project.settings.grid,metrics.ground);const grid=new THREE.GridHelper(layout.size,layout.divisions,0x394a5d,0x263342);grid.position.set(...layout.center);grid.material.transparent=true;grid.material.opacity=.35;grid.material.depthWrite=false;grid.userData.layout=layout;this.grid=grid;this.helpers.add(grid);this.orientGrid();
  const axes=new THREE.AxesHelper(1);axes.material.transparent=true;axes.material.opacity=.7;this.helpers.add(axes);
  for(const o of project.objects){let root;
   if(o.role==='CAMERA'){root=new THREE.PerspectiveCamera(40,1,.03,1000);root.up.set(0,0,1);const iconGroup=new THREE.Group();
    const piece=(geometry,color,position)=>{const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.5}));mesh.position.set(...position);mesh.userData.objectId=o.id;iconGroup.add(mesh);return mesh;};
    piece(new THREE.BoxGeometry(.72,.5,.52),0x889eaf,[0,0,.12]);
    piece(new THREE.BoxGeometry(.32,.12,.22),0x526779,[0,.31,.12]);
    const lens=new THREE.CylinderGeometry(.22,.25,.42,24);lens.rotateX(Math.PI/2);piece(lens,0x394b5b,[0,0,-.34]);
    const glass=new THREE.CylinderGeometry(.18,.18,.025,24);glass.rotateX(Math.PI/2);piece(glass,0x9bdbdf,[0,0,-.56]);
    const direction=new THREE.ArrowHelper(new THREE.Vector3(0,0,-1),new THREE.Vector3(0,0,-.6),1.15,0xc3ef88,.25,.14);direction.traverse(child=>child.userData.objectId=o.id);iconGroup.add(direction);
    this.helpers.add(iconGroup);root.userData.icon=iconGroup;
    const guide=new THREE.Group(),makeLine=color=>new THREE.Line(new THREE.BufferGeometry().setFromPoints([vec([0,0,0]),vec([0,0,0])]),new THREE.LineDashedMaterial({color,dashSize:.16,gapSize:.1,depthTest:false}));
    const sight=makeLine(0x91cfff),route=makeLine(0xe7b86a),markers=[0xc3ef88,0xe7b86a].map(color=>new THREE.Mesh(new THREE.SphereGeometry(.13,16,12),new THREE.MeshBasicMaterial({color,depthTest:false})));
    guide.add(sight,route,...markers);guide.traverse(child=>child.renderOrder=5);guide.visible=false;this.helpers.add(guide);root.userData.shotGuide={group:guide,sight,route,markers};}
   else {root=new THREE.Group();for(const part of o.parts||[]){let geo;if(part.shape==='BOX')geo=new THREE.BoxGeometry(1,1,1);else if(part.shape==='SPHERE')geo=new THREE.SphereGeometry(.5,24,16);else if(part.shape==='CYLINDER'||part.shape==='CONE'){geo=part.shape==='CONE'?new THREE.CylinderGeometry(.5*(part.topRatio||0),.5,1,32):new THREE.CylinderGeometry(.5,.5,1,32);geo.rotateX(Math.PI/2);}else{geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(part.vertices.flat(),3));geo.setIndex(part.triangles.flat());geo.computeVertexNormals();}const mesh=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:o.locatorColor||0xb7bdc4,roughness:.85,metalness:0,side:THREE.DoubleSide}));mesh.applyMatrix4(new THREE.Matrix4().fromArray(part.matrix));mesh.userData.objectId=o.id;root.add(mesh);}}
   root.userData.objectId=o.id;this.roots.set(o.id,root);this.content.add(root);
   if(o.modelSource){
    const target=root,source=o.modelSource;
    new GLTFLoader().load('/models/'+encodeURIComponent(source.name),gltf=>{
     if(this.roots.get(o.id)!==target){this.disposeTree(gltf.scene);return;}
     this.disposeTree(target);applyModelMaterialFallback(gltf);
     const converted=new THREE.Group();converted.rotation.x=Math.PI/2;converted.position.set(-source.center[0],-source.center[1],-source.center[2]);converted.add(gltf.scene);const calibrated=new THREE.Group();calibrated.rotation.z=source.localYaw||0;calibrated.add(converted);target.add(calibrated);
     gltf.scene.traverse(child=>{child.userData.objectId=o.id;});
     target.userData.mixer=new THREE.AnimationMixer(gltf.scene);target.userData.clips={};
     for(const name of new Set((o.segments||[]).map(s=>s.motion?.name).filter(Boolean))){
      new GLTFLoader().load('/motions/'+encodeURIComponent(name),asset=>{
       if(this.roots.get(o.id)!==target){this.disposeTree(asset.scene);return;}
       if(asset.animations.length!==1){this.events.message?.('动作文件没有唯一动画片段',true);return;}
       target.userData.clips[name]=asset.animations[0];this.disposeTree(asset.scene);this.update(this.time);
      },undefined,error=>this.events.message?.('动作加载失败：'+error.message,true));
     }

    },undefined,error=>this.events.message?.('原始模型加载失败：'+source.name+'；当前显示简化网格。'+error.message,true));
   }
   if(o.role==='TARGET'){const target=new THREE.Mesh(new THREE.SphereGeometry(.18,16,12),new THREE.MeshBasicMaterial({color:0xc3ef88,wireframe:true,depthTest:false}));target.userData.objectId=o.id;target.renderOrder=4;this.helpers.add(target);root.userData.icon=target;const link=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),new THREE.LineDashedMaterial({color:0x8fae70,dashSize:.15,gapSize:.12,transparent:true,opacity:.7,depthTest:false}));link.renderOrder=2;this.helpers.add(link);root.userData.controlLink=link;}
   if(o.role==='ACTOR'||o.role==='PROP'){const arrows=new THREE.Group();arrows.add(new THREE.ArrowHelper(new THREE.Vector3(0,o.frontAxis==='-Y'?-1:1,0),new THREE.Vector3(),1,0xa1d783,.2,.12),new THREE.ArrowHelper(new THREE.Vector3(0,o.frontAxis==='-Y'?1:-1,0),new THREE.Vector3(),.7,0xe28585,.15,.1));this.helpers.add(arrows);root.userData.arrows=arrows;}
   if(o.nodes?.length)try{this.motions.set(o.id,new SegmentMotion(o));}catch{}
  }
  this.refreshPaths();this.update(this.time);this.select(this.selected,this.nodeIndex);this.resize();
 }
 refreshPaths(){if(!this.project)return;this.disposeTree(this.pathGroup);
  for(const source of this.project.objects){const o=editObject(this.project,source);if(o.hidden)continue;const motion=new SegmentMotion(o);
   motion.segments.forEach((s,i)=>{const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(motion.arcs[i].points.map(vec)),new (this.editLayer==='CAMERA'?THREE.LineDashedMaterial:THREE.LineBasicMaterial)({...(this.editLayer==='CAMERA'?{dashSize:.15,gapSize:.1}:{}),color:s.id===this.segmentId?0xc3ef88:0xe7b86a,depthTest:false}));line.computeLineDistances();line.userData={objectId:o.id,segmentId:s.id};line.renderOrder=3;this.pathGroup.add(line);});
   o.nodes?.forEach((n,i)=>{const dot=new THREE.Mesh(new THREE.SphereGeometry(i===this.nodeIndex&&o.id===this.selected?.075:.06,12,8),new THREE.MeshBasicMaterial({color:i===this.nodeIndex&&o.id===this.selected?0xc3ef88:0xe7b86a}));dot.position.fromArray(n.position);dot.userData={node:i,objectId:o.id};this.pathGroup.add(dot);});
  }
 }
 contextMenu(e){e.preventDefault();if(this.editLayer==='CAMERA')return;if(this.pointer&&Math.hypot(e.clientX-this.pointer[0],e.clientY-this.pointer[1])>5)return;this.rayFromPointer(e);this.ray.params.Line.threshold=this.camera.isOrthographicCamera?.1/this.camera.zoom:.12;const hits=this.ray.intersectObjects(this.pathGroup.children,false).filter(h=>h.object.userData.segmentId||this.project.objects.find(o=>o.id===h.object.userData.objectId)?.nodes[h.object.userData.node]?.dwell>0);if(hits.length){const d=hits[0].object.userData;this.events.segment?.(d.objectId,d.segmentId||this.project.objects.find(o=>o.id===d.objectId).nodes[d.node].id,e.clientX,e.clientY);return;}const objects=this.ray.intersectObjects(this.content.children,true).filter(h=>{const data=this.project.objects.find(o=>o.id===h.object.userData.objectId);return data&&!data.hidden&&data.role!=='ENV';});if(objects.length){this.events.objectMenu?.(objects[0].object.userData.objectId,e.clientX,e.clientY);return;}const point=this.ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,0,1),0),new THREE.Vector3());if(point)this.events.emptyMenu?.(point.toArray(),e.clientX,e.clientY);else this.events.message?.('请在俯视或自由视图选择地面位置');}

 select(id,nodeIndex=-1){this.selected=id;this.nodeIndex=nodeIndex;this.control.detach();const data=editObject(this.project,this.project?.objects.find(o=>o.id===id)),root=this.roots.get(id);
  if(data?.role==='CAMERA'&&data.viewMode==='LOCK'&&!this.startEdit){const target=this.project.objects.find(o=>o.id===data.target),owner=this.project.objects.find(o=>o.id===target?.follow);if(owner){const ss=edges(owner),i=ss.findIndex(s=>this.time>=s.startTime&&this.time<s.endTime);if(i>0&&data.shots?.[ss[i].id]?.controlVersion!==3&&data.shots?.[ss[i].id]?.inherit)return;}}
  if(this.editLayer==='CAMERA'&&data&&!['CAMERA','TARGET'].includes(data.role))return;if(this.editLayer==='OBJECT'&&currentShot(this.project)&&['CAMERA','TARGET'].includes(data?.role))return;
  if(this.startEdit?.camera===id){if(this.startEdit.locked)return;this.handle.position.fromArray(this.startEdit.position);const cfg=currentShot(this.project)?.cfg;this.handle.quaternion.fromArray(cfg?.start.quaternion||[0,0,0,1]);this.control.attach(this.handle);this.control.setMode(this.tool==='rotate'?'rotate':'translate');return;}
  if(!root||!data||data.locked||data.hidden||this.tool==='path'||this.tool==='select')return;
  if(this.tool==='translate'&&data.nodes?.length){this.nodeIndex=Math.max(0,Math.min(nodeIndex,data.nodes.length-1));this.handle.position.fromArray(data.nodes[this.nodeIndex].position);this.handle.quaternion.identity();this.control.attach(this.handle);}
  else{this.nodeIndex=-1;if(data.role==='TARGET'&&this.controlCamera(id)&&this.tool==='translate'){this.handle.position.copy(root.userData.icon.position);this.handle.quaternion.identity();this.control.attach(this.handle);}else this.control.attach(root);}
  this.control.setMode(this.tool==='orbit'?'rotate':this.tool);this.control.showZ=!(data.lockZ&&this.tool==='translate');this.control.showX=true;this.control.showY=true;
  this.control.setTranslationSnap(this.project.settings.snap?this.project.settings.grid:null);
  if(this.tool==='orbit'&&data.role==='CAMERA'&&data.target){const t=this.roots.get(data.target);if(t){this.handle.position.copy(t.position);this.handle.quaternion.identity();this.control.attach(this.handle);this.control.showX=false;this.control.showY=false;this.control.showZ=true;}}
 }
 setTool(tool){this.tool=tool;this.select(this.selected,this.nodeIndex);}
 orientGrid(){if(!this.grid)return;this.grid.rotation.set(this.view==='TOP'||this.view==='FREE'?Math.PI/2:0,0,this.view==='SIDE'?Math.PI/2:0);}
 setView(mode){this.view=mode;this.orientGrid();const target=this.orbit?.target.clone()||new THREE.Vector3();this.camera=mode==='FREE'?this.perspective:this.ortho;this.camera.up.set(...(mode==='TOP'?[0,1,0]:[0,0,1]));if(mode!=='FREE'){const p=mode==='TOP'?[0,0,35]:mode==='FRONT'?[0,-35,0]:[35,0,0];this.camera.position.copy(target).add(vec(p));this.camera.lookAt(target);}this.orbit.object=this.camera;this.orbit.enableRotate=mode==='FREE';this.control.camera=this.camera;this.orbit.update();this.resize();}
 controlCamera(id){const cams=this.project?.objects.filter(o=>o.role==='CAMERA'&&o.target===id)||[];return cams.find(o=>o.id===this.project.activeCamera)||cams[0];}
 focusScene(ids){const box=new THREE.Box3();for(const id of ids){const root=this.roots.get(id);if(root)box.union(new THREE.Box3().setFromObject(root));}if(box.isEmpty())return this.focus(null);const center=box.getCenter(new THREE.Vector3()),extent=box.getSize(new THREE.Vector3()),aspect=Math.max(.1,this.container.clientWidth/Math.max(1,this.container.clientHeight)),size=Math.max(3,extent.y,extent.x/aspect,extent.z)*1.18,delta=center.clone().sub(this.orbit.target);this.camera.position.add(delta);if(this.view==='FREE'){const direction=this.camera.position.clone().sub(center).normalize();this.camera.position.copy(center).addScaledVector(direction,size*1.5);}this.orbit.target.copy(center);this.ortho.zoom=12/size;this.ortho.updateProjectionMatrix();this.orbit.update();}
 focus(id){const root=this.roots.get(id);let center=new THREE.Vector3(),size=7;if(root){const box=new THREE.Box3().setFromObject(root);if(!box.isEmpty()){center=box.getCenter(center);size=Math.max(3,box.getSize(new THREE.Vector3()).length()*1.8);}else{center.copy(root.userData.icon?.position||root.position);if(root.userData.controlLink){const c=this.controlCamera(id),cr=this.roots.get(c?.id);if(cr){size=Math.max(5,cr.position.distanceTo(center)*1.5);center.add(cr.position).multiplyScalar(.5);}}}}const delta=center.clone().sub(this.orbit.target);this.camera.position.add(delta);if(this.view==='FREE'){const direction=this.camera.position.clone().sub(center).normalize();this.camera.position.copy(center).addScaledVector(direction,size*1.5);}this.orbit.target.copy(center);this.ortho.zoom=12/size;this.ortho.updateProjectionMatrix();this.orbit.update();}
 resize(){const w=Math.max(1,this.container.clientWidth),h=Math.max(1,this.container.clientHeight);this.renderer.setSize(w,h,false);this.referenceAspect??=w/h;const fit=Math.max(1,this.referenceAspect/(w/h));this.ortho.left=-6*w/h*fit;this.ortho.right=6*w/h*fit;this.ortho.top=6*fit;this.ortho.bottom=-6*fit;this.perspective.fov=THREE.MathUtils.radToDeg(2*Math.atan(Math.tan(THREE.MathUtils.degToRad(45/2))*fit));this.ortho.updateProjectionMatrix();this.perspective.aspect=w/h;this.perspective.updateProjectionMatrix();const ratio=(this.project?.settings.width||1280)/(this.project?.settings.height||720);let pw=this.preview.clientWidth,ph=this.preview.clientHeight;if(pw/ph>ratio)pw=ph*ratio;else ph=pw/ratio;this.previewRenderer.setSize(Math.max(1,pw),Math.max(1,ph),false);this.previewRenderer.domElement.style.width=`${pw}px`;this.previewRenderer.domElement.style.height=`${ph}px`;}
 update(time){this.time=time;if(!this.project)return;this.warning='';
  for(const o of this.project.objects){const root=this.roots.get(o.id);if(!root)continue;if(this.dragging&&this.control.object===root)continue;
   try{const state=o.role==='CAMERA'?this.evaluator.camera(o,time,this.previewSegment):this.evaluator.pose(o,time);if(o.role==='CAMERA')validCameraState(state);const rotation=o.role==='CAMERA'?cameraQuaternion(state):state.quaternion;if(!finiteVector(state.position)||!finiteVector(rotation,4))throw Error('对象变换无效');root.position.fromArray(state.position);root.quaternion.fromArray(rotation);if(state.warning)this.warning=state.warning;root.scale.fromArray(o.scale);root.visible=!o.hidden;
    if(o.role==='CAMERA'){root.userData.lastValid=state;root.userData.currentLens=state.lens;root.userData.focus=state.focus;const ratio=this.project.settings.width/this.project.settings.height;root.aspect=ratio;root.fov=THREE.MathUtils.radToDeg(2*Math.atan(36/(2*state.lens*ratio)));root.updateProjectionMatrix();}
   }catch(e){this.warning=e.message;if(o.role==='CAMERA'&&this.startEdit?.camera===o.id)root.position.fromArray(this.startEdit.position);}
   const mixer=root.userData.mixer;if(mixer){const seg=edges(o).find(s=>s.motion&&time>=s.startTime&&time<s.endTime),clip=seg&&root.userData.clips?.[seg.motion.name];const key=clip?seg.id:null;if(root.userData.motionKey!==key){mixer.stopAllAction();root.userData.motionKey=key;if(clip)mixer.clipAction(clip).reset().play();}if(clip)mixer.setTime((time-seg.startTime)%clip.duration);}
   root.updateMatrixWorld(true);
   if(root.userData.arrows){root.userData.arrows.position.copy(root.position);root.userData.arrows.quaternion.copy(root.quaternion);root.userData.arrows.visible=!o.hidden;}
   if(root.userData.icon){root.userData.icon.position.copy(root.position);root.userData.icon.quaternion.copy(root.quaternion);root.userData.icon.visible=!o.hidden;}
  }
  for(const c of this.project.objects.filter(o=>o.role==='CAMERA'))this.updateShotGuide(c,time);
  for(const o of this.project.objects.filter(o=>o.role==='TARGET')){
   const c=this.controlCamera(o.id),root=this.roots.get(o.id);if(!c)continue;const cr=this.roots.get(c.id),forward=vec([0,0,-1]).applyQuaternion(cr.quaternion),aim=c.viewMode==='FREE'?cr.position.clone().add(forward):(cr.userData.focus?vec(cr.userData.focus):root.position);
   const lens=cr.userData.currentLens??keyValue(c.lenses||[],time,c.lens||50),scale=c.controlScale||controlScale(cr.position.distanceTo(root.position),lens);
   root.userData.icon.position.fromArray(controlPoint(cr.position.toArray(),aim.toArray(),lens,scale,forward.toArray()));
   const pixelWorld=this.camera.isOrthographicCamera?(this.camera.top-this.camera.bottom)/this.camera.zoom/Math.max(1,this.container.clientHeight):2*this.camera.position.distanceTo(root.userData.icon.position)*Math.tan(THREE.MathUtils.degToRad(this.camera.fov/2))/Math.max(1,this.container.clientHeight);root.userData.icon.scale.setScalar(Math.max(.5,pixelWorld*8/.18));
   const link=root.userData.controlLink;link.geometry.setFromPoints([cr.position,root.userData.icon.position]);link.computeLineDistances();link.visible=!o.hidden&&!c.hidden;
   if(this.selected===o.id&&this.control.object===this.handle&&this.tool==='translate'&&!o.nodes?.length&&!this.dragging&&!this.targetDrag)this.handle.position.copy(root.userData.icon.position);
  }
 }
 updateShotGuide(c,time){
  const root=this.roots.get(c.id),guide=root.userData.shotGuide,owner=currentShot(this.project)?.owner||followOwner(this.project,c),ss=owner?units(owner):[];
  const sid=currentShot(this.project)?.unit.id||this.previewSegment||this.segmentId,s=ss.find(s=>s.id===sid)||ss.find((s,i)=>time>=s.startTime&&(time<s.endTime||i===ss.length-1&&time<=s.endTime));
  guide.group.visible=false;if(c.hidden||c.id!==this.project.activeCamera||!s||c.shots?.[s.id]?.motion!=='DOLLY')return;
  try{
   if(guide.evaluator!==this.evaluator||guide.sid!==s.id){
    const samples=Array.from({length:33},(_,i)=>vec(this.evaluator.camera(c,s.startTime+(s.endTime-s.startTime)*i/32,s.id).position));
    guide.route.geometry.setFromPoints(samples);guide.route.computeLineDistances();guide.markers[0].position.copy(samples[0]);guide.markers[1].position.copy(samples.at(-1));guide.evaluator=this.evaluator;guide.sid=s.id;
   }
   if(root.userData.focus){guide.sight.geometry.setFromPoints([root.position,vec(root.userData.focus)]);guide.sight.computeLineDistances();}
   guide.group.visible=true;
  }catch{ /* Invalid shot settings stay editable; the inspector reports the conflict. */ }
 }
 render(){
  if(!this.project)return;const helper=this.control.getHelper();
  const draw=(renderer,camera,label)=>{try{if(!renderer.getContext().isContextLost())renderer.render(this.scene,camera);this.renderErrors??={};delete this.renderErrors[label];}catch(e){this.renderErrors??={};if(this.renderErrors[label]!==e.message){console.error(label,e);this.events.message?.(label+'：'+e.message,true);this.renderErrors[label]=e.message;}}};
  try{this.helpers.visible=this.helpersOn;helper.visible=!!this.control.object;this.scene.background.set('#131922');draw(this.renderer,this.camera,'工作区渲染失败');
   const camera=this.roots.get(this.project.activeCamera);this.helpers.visible=false;helper.visible=false;this.scene.background.set('#343b44');if(camera?.isCamera)draw(this.previewRenderer,camera,'摄影机预览失败');else this.previewRenderer.clear();
  }finally{this.helpers.visible=this.helpersOn;helper.visible=!!this.control.object;}
 }
 rayFromPointer(e){const r=this.container.getBoundingClientRect();this.mouse.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);this.ray.setFromCamera(this.mouse,this.camera);}
 targetDragStart(e){
  if(e.button!==0||!this.helpersOn||this.tool==='path'||this.tool==='orbit'||this.editLayer==='OBJECT'&&currentShot(this.project))return;
  this.rayFromPointer(e);
  const targets=this.project.objects.filter(o=>o.role==='TARGET'&&!o.hidden&&!o.locked);
  const hits=this.ray.intersectObjects(targets.map(o=>this.roots.get(o.id).userData.icon),false);
  if(!hits.length)return;
  const data=targets.find(o=>o.id===hits[0].object.userData.objectId);
  if(data.nodes?.length)return;
  if(this.control.axis&&this.selected===data.id&&this.tool==='translate')return;
  e.stopImmediatePropagation();e.preventDefault();
  this.events.select?.(data.id,false,-1);this.events.start?.();
  const position=this.roots.get(data.id).userData.icon.position.clone();
  const normal=this.view==='TOP'?new THREE.Vector3(0,0,1):this.view==='FRONT'?new THREE.Vector3(0,1,0):this.view==='SIDE'?new THREE.Vector3(1,0,0):this.camera.getWorldDirection(new THREE.Vector3());
  const plane=new THREE.Plane().setFromNormalAndCoplanarPoint(normal,position);
  const point=this.ray.ray.intersectPlane(plane,new THREE.Vector3());
  this.targetDrag={plane,offset:position.clone().sub(point||position),id:e.pointerId};this.orbit.enabled=false;
  this.renderer.domElement.setPointerCapture(e.pointerId);
 }
 targetDragMove(e){if(!this.targetDrag)return;e.stopImmediatePropagation();this.rayFromPointer(e);const point=this.ray.ray.intersectPlane(this.targetDrag.plane,new THREE.Vector3());if(point){point.add(this.targetDrag.offset);if(this.project.settings.snap)point.toArray().forEach((v,i)=>point.setComponent(i,Math.round(v/this.project.settings.grid)*this.project.settings.grid));this.targetDrag.plane.projectPoint(point,point);this.events.transform?.({position:point.toArray(),rotation:[0,0,0],node:-1,directTarget:true});}}
 targetDragEnd(e){if(!this.targetDrag)return;e.stopImmediatePropagation();if(this.renderer.domElement.hasPointerCapture(e.pointerId))this.renderer.domElement.releasePointerCapture(e.pointerId);this.targetDrag=null;this.orbit.enabled=true;this.events.end?.();}
 pointerUp(e){if(e.button!==0||!this.pointer||Math.hypot(e.clientX-this.pointer[0],e.clientY-this.pointer[1])>4||this.control.axis)return;const r=this.container.getBoundingClientRect();this.mouse.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);this.ray.setFromCamera(this.mouse,this.camera);
  if(this.tool==='path'){if(this.view==='FREE'){this.events.message?.('布路径请先切换俯视、前视或侧视');return;}const data=editObject(this.project,this.project.objects.find(o=>o.id===this.selected));if(!data)return;const base=data.nodes?.at(-1)?.position||data.position,normal=this.view==='TOP'?[0,0,1]:this.view==='FRONT'?[0,1,0]:[1,0,0];const plane=new THREE.Plane().setFromNormalAndCoplanarPoint(vec(normal),vec(base));const point=this.ray.ray.intersectPlane(plane,new THREE.Vector3());if(point)this.events.pathPoint?.(point.toArray());return;}
  const hits=this.ray.intersectObjects([...this.content.children,...this.helpers.children],true).filter(h=>h.object.userData.objectId);if(hits.length){const hit=hits[0].object;this.events.select?.(hit.userData.objectId,e.shiftKey,hit.userData.node??-1);}else if(!e.shiftKey)this.events.select?.(null,false,-1);
 }
 bounds(id){const root=this.roots.get(id);return root?new THREE.Box3().setFromObject(root):null;}
 worldMatrix(id){const root=this.roots.get(id);root?.updateMatrixWorld(true);return root?.matrixWorld.clone();}
}
