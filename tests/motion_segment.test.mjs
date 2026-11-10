import test from 'node:test';
import assert from 'node:assert/strict';
import {splitSegment} from '../web/segments.js';
test('splitting a segment preserves independent bindings on both pieces',()=>{
 const o={id:'a',position:[0,0,0],nodes:[{id:'n1',position:[0,0,0],time:0,dwell:0},{id:'n2',position:[2,0,0],time:2,dwell:0}],segments:[{id:'s',start:'n1',end:'n2',startTime:0,endTime:2,motion:{name:'walk.glb',clip:'walk'}}],smooth:false};
 splitSegment({objects:[o]},o,'s');assert.equal(o.segments.length,2);assert.deepEqual(o.segments.map(s=>s.motion.name),['walk.glb','walk.glb']);assert.notEqual(o.segments[0].motion,o.segments[1].motion);
});
