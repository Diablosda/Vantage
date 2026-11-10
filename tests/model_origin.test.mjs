import test from 'node:test';
import assert from 'node:assert/strict';
import {calibrateOrigin} from '../web/model_origin.js';
test('prop and actor pivot calibration preserve motion and convert through local yaw',()=>{
 const o={id:'a',role:'PROP',modelSource:{center:[0,0,0],localYaw:Math.PI/2},parts:[{matrix:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],vertices:[[0,0,0],[2,4,6]]}],position:[3,2,1],nodes:[{position:[3,2,1]}]};
 const p={objects:[o,{shots:{s:{focusTarget:'a',focusLocal:[1,2,3]}}}]};calibrateOrigin(p,o);
 assert.ok(Math.abs(o.modelSource.center[0]-2)<1e-8);assert.ok(Math.abs(o.modelSource.center[1]+1)<1e-8);assert.equal(o.modelSource.center[2],3);assert.deepEqual(o.parts[0].matrix.slice(12,15),[-1,-2,-3]);assert.deepEqual(o.position,[3,2,1]);assert.deepEqual(o.nodes[0].position,[3,2,1]);assert.deepEqual(p.objects[1].shots.s.focusLocal,[0,0,0]);
 calibrateOrigin(p,o,'ACTOR');assert.equal(o.modelSource.center[2],0);assert.deepEqual(o.parts[0].matrix.slice(12,15),[-1,-2,0]);
});
