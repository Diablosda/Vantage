import test from 'node:test';
import assert from 'node:assert/strict';
import {replaceModelGeometry} from '../web/model_replace.js';

test('replacement retains identity, movement, transforms, and relationships',()=>{
 const target={id:'actor',name:'主角',role:'ACTOR',parts:[{shape:'BOX'}],position:[1,2,3],rotation:[0,0,1],scale:[2,2,2],nodes:[{position:[1,2,3],time:0}],segments:[{id:'segment',speed:2}],angles:[{time:1,rotation:[0,0,2]}],orientation:'PATH',follow:'other',locked:true,hidden:false};
 const before=structuredClone(target),model={parts:[{shape:'MESH'}],modelSource:{name:'actor.glb',center:[0,0,0]}};
 replaceModelGeometry(target,model);
 assert.deepEqual(target.parts,model.parts);assert.deepEqual(target.modelSource,model.modelSource);
 delete target.parts;delete target.modelSource;delete before.parts;assert.deepEqual(target,before);
});
test('invalid replacement leaves existing object intact',()=>{
 const target={id:'actor',parts:[{shape:'BOX'}]};const before=structuredClone(target);
 assert.throws(()=>replaceModelGeometry(target,{parts:[]}));assert.deepEqual(target,before);
});
