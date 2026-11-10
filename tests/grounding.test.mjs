import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../web/vendor/three/build/three.module.js';
import {lowestPoint,groundObject} from '../web/grounding.js';
const part=(shape,size=[1,1,1],position=[0,0,0])=>({shape,matrix:new THREE.Matrix4().compose(new THREE.Vector3(...position),new THREE.Quaternion(),new THREE.Vector3(...size)).toArray()});
const obj=parts=>({role:'PROP',parts,position:[2,3,0],rotation:[0,0,0],scale:[1,1,1],nodes:[]});
const pose=o=>({position:[...o.position],quaternion:new THREE.Quaternion().setFromEuler(new THREE.Euler(...o.rotation,'ZYX')).toArray()});
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
test('sphere raises out of ground and lowers from air exactly; operation is idempotent',()=>{
 const o=obj([part('SPHERE',[2,2,2])]);near(groundObject(o,pose(o)),1);near(o.position[2],1);
 o.position[2]=5;near(groundObject(o,pose(o),-.15),-4.15);near(lowestPoint(o,pose(o)),-.15);near(groundObject(o,pose(o),-.15),0);
});
test('rotated nonuniform primitives use their true support, including offsets and negative scale',()=>{
 const o=obj([part('BOX',[2,4,6],[0,0,1])]);o.rotation=[Math.PI/2,0,0];o.scale=[1,2,-1];near(lowestPoint(o,pose(o)),-4);groundObject(o,pose(o),.3);near(lowestPoint(o,pose(o)),.3);
 const sphere=obj([part('SPHERE',[2,4,6])]);sphere.rotation=[Math.PI/4,0,0];near(lowestPoint(sphere,pose(sphere)),-Math.sqrt(6.5));
 for(const shape of ['CYLINDER','CONE']){const c=obj([part(shape,[2,2,4])]);c.rotation=[Math.PI/2,0,0];near(lowestPoint(c,pose(c)),-1);groundObject(c,pose(c),2);near(lowestPoint(c,pose(c)),2);}
});
test('multipart mesh minimum uses all vertices and part matrices; full path translates without retiming',()=>{
 const o=obj([part('BOX'),{shape:'MESH',vertices:[[0,0,-3],[1,0,2],[0,1,0]],matrix:part('BOX',[1,1,2],[0,0,1]).matrix}]);
 o.nodes=[{position:[2,3,2],time:0},{position:[4,5,6],time:3}];const snapshot=structuredClone(o);
 const currentPose={...pose(o),position:[3,4,4]};near(groundObject(o,currentPose),1);near(o.position[2],1);assert.deepEqual(o.nodes.map(n=>n.position),[[2,3,3],[4,5,7]]);assert.equal(o.nodes[1].time,3);
 const roundtrip=JSON.parse(JSON.stringify(o));assert.deepEqual(roundtrip,o);Object.assign(o,snapshot);assert.deepEqual(o,snapshot);
});
test('locked, imported, followed and invalid geometry fail without moving data',()=>{
 for(const patch of [{locked:true},{modelSource:{}},{follow:'other'},{parts:[]},{parts:[{shape:'SPHERE',matrix:Array(16).fill(NaN)}]}]){
  const o={...obj([part('SPHERE')]),...patch},before=structuredClone(o);assert.throws(()=>groundObject(o,pose(o)));assert.deepEqual(o,before);
 }
});
