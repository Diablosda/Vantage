import test from 'node:test';
import assert from 'node:assert/strict';
import {controlScale,controlReach,controlLens,controlPoint} from '../web/camera_control.js';
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`);
test('lens / distance are reversible including limits',()=>{const scale=controlScale(10,50);for(const f of [1,18,35,50,85,1000])close(controlLens(controlReach(f,scale),scale),f);assert.equal(controlLens(0,scale),1);assert.equal(controlLens(10000,scale),1000);});
test('changing lens moves handle on same sight line without moving aim anchor',()=>{const camera=[6,-8,5],aim=[0,0,1],scale=controlScale(Math.hypot(6,8,4),50);controlPoint(camera,aim,50,scale).forEach((v,i)=>close(v,aim[i]));const p=controlPoint(camera,aim,85,scale);assert.ok(p[0]<0&&p[1]>0&&p[2]<1);close((p[0]-6)/-6,(p[1]+8)/8);assert.deepEqual(aim,[0,0,1]);});
test('following changes direction but keeps focal handle radius',()=>{const camera=[2,-4,3],scale=.2;for(const aim of [[0,0,1],[5,2,1],[2,-4,3]]){const p=controlPoint(camera,aim,50,scale);close(Math.hypot(...p.map((v,i)=>v-camera[i])),controlReach(50,scale));}});
