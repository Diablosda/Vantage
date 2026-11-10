import test from 'node:test';import assert from 'node:assert/strict';import {scaleSceneObjects,setSceneScale} from '../web/scene_import.js';
test('scene scale transforms objects and lights exactly once and preserves local geometry',()=>{const objects=[{position:[2,3,1],scale:[1,1,1],sceneSource:{kind:'MESH'},parts:[{vertices:[[1,0,0]]}]},{position:[3,4,5],scale:[1,1,1],sceneSource:{kind:'LIGHT'}}];scaleSceneObjects(objects,2);assert.deepEqual(objects[0].position,[4,6,2]);assert.deepEqual(objects[0].scale,[2,2,2]);assert.deepEqual(objects[0].parts[0].vertices,[[1,0,0]]);assert.deepEqual(objects[1].position,[6,8,10]);assert.equal(objects[1].sceneSource.unitScale,2);assert.throws(()=>scaleSceneObjects([],0));});

test('calibration scales background and lamps around a fixed pivot, preserving actors and paths',()=>{
 const bg={role:'ENV',position:[4,8,0],scale:[1,2,1],hidden:true,locked:true,initialState:{position:[2,4,0],scale:[1,1,1]},parts:[{vertices:[[1,0,0]]}]};
 const light={role:'ENV',position:[2,4,4],scale:[1,1,1],sceneSource:{kind:'LIGHT'}};
 const actor={role:'ACTOR',position:[2,4,0],scale:[1,1,1],nodes:[{position:[3,4,0]}]};
 const camera={role:'CAMERA',position:[8,9,4],scale:[1,1,1]};
 const p={settings:{grid:.5},objects:[bg,light,actor,camera]},before=structuredClone(p);
 setSceneScale(p,.5,[2,4,0]);assert.deepEqual(bg.position,[3,6,0]);assert.deepEqual(bg.scale,[.5,1,.5]);assert.deepEqual(light.position,[2,4,2]);
 assert.deepEqual(actor,before.objects[2]);assert.deepEqual(camera,before.objects[3]);assert.equal(p.settings.grid,.5);assert.deepEqual(bg.initialState.scale,[.5,.5,.5]);
 const loaded=JSON.parse(JSON.stringify(p));setSceneScale(loaded,1,[999,999,999]);assert.deepEqual(loaded.objects,before.objects);assert.deepEqual(loaded.settings.sceneScalePivot,[2,4,0]);
 assert.throws(()=>setSceneScale(p,0,[0,0,0]));assert.throws(()=>setSceneScale({settings:{},objects:[]},1,[0,0,0]));
});
