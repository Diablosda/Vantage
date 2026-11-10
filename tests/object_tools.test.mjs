import test from 'node:test';import assert from 'node:assert/strict';
import {gridMove,translateObjectAndPath,canColor} from '../web/object_tools.js';
test('direction keys move one grid interval on ground, oriented to view',()=>{
 assert.deepEqual(gridMove('ArrowUp',.5,[1,0]),[0,.5,0]);assert.deepEqual(gridMove('ArrowLeft',.5,[1,0]),[-.5,0,0]);
 assert.deepEqual(gridMove('ArrowRight',2,[0,1]),[0,2,0]);assert.deepEqual(gridMove('ArrowUp',2,[0,1]),[-2,0,0]);
 assert.deepEqual(gridMove('ArrowDown',1,[-.9,.2]),[0,1,0]);assert.equal(gridMove('x',1,[1,0]),null);assert.throws(()=>gridMove('ArrowUp',0,[1,0]));
});
test('moving a tracked character translates all path points and keeps their heights and timing',()=>{
 const o={role:'ACTOR',position:[3,4,7],nodes:[{position:[3,4,7],time:0},{position:[5,9,8],time:2}]};
 translateObjectAndPath(o,[.5,-.5,0]);assert.deepEqual(o.position,[3.5,3.5,7]);assert.deepEqual(o.nodes.map(n=>n.position),[[3.5,3.5,7],[5.5,8.5,8]]);assert.equal(o.nodes[1].time,2);
 const before=structuredClone(o);assert.throws(()=>translateObjectAndPath(o,[1e9,0,0]));assert.deepEqual(o,before);
});
test('locator color applies to created white models only',()=>{const o={role:'ACTOR',parts:[{}]};assert.equal(canColor(o),true);assert.equal(canColor({...o,modelSource:{}}),false);assert.equal(canColor({...o,sceneSource:{}}),false);assert.equal(canColor({...o,role:'CAMERA'}),false);});
