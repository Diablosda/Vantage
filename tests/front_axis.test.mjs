import test from 'node:test';
import assert from 'node:assert/strict';
import {Evaluator} from '../web/segments.js';
import * as THREE from '../web/vendor/three/build/three.module.js';
test('new negative-Y and legacy positive-Y objects face the path without changing legacy projects',()=>{
 const mk=frontAxis=>({id:frontAxis||'legacy',role:'ACTOR',position:[0,0,0],rotation:[0,0,0],scale:[1,1,1],orientation:'PATH',frontAxis,nodes:[{id:'a',position:[0,0,0],time:0,dwell:0},{id:'b',position:[0,3,0],time:3,dwell:0}],segments:[{id:'s',start:'a',end:'b',startTime:0,endTime:3}]});
 for(const axis of [undefined,'-Y']){const o=mk(axis),q=new THREE.Quaternion(...new Evaluator({objects:[o]}).pose(o,1).quaternion),front=new THREE.Vector3(0,axis?-1:1,0).applyQuaternion(q);assert.ok(front.y>.99999);}
});
