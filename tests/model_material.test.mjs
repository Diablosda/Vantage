import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../web/vendor/three/build/three.module.js';
import {applyModelMaterialFallback} from '../web/model_material.js';
test('only meshes without authored materials or vertex colors receive a gray fallback',()=>{
 const original=new THREE.MeshStandardMaterial({color:0xffffff,metalness:1});
 const authored=new THREE.MeshStandardMaterial({color:0xff0000});
 const bare=new THREE.Mesh(new THREE.BufferGeometry(),original);
 const coloredGeometry=new THREE.BufferGeometry();coloredGeometry.setAttribute('color',new THREE.Float32BufferAttribute([1,0,0],3));
 const vertexColored=new THREE.Mesh(coloredGeometry,original),painted=new THREE.Mesh(new THREE.BufferGeometry(),authored);
 const scene=new THREE.Group();scene.add(bare,vertexColored,painted);
 const associations=new Map([[bare,{meshes:0,primitives:0}],[vertexColored,{meshes:0,primitives:1}],[painted,{meshes:0,primitives:2}]]);
 const gltf={scene,parser:{associations,json:{meshes:[{primitives:[{}, {attributes:{COLOR_0:0}}, {material:0}]}]}}};
 applyModelMaterialFallback(gltf);
 assert.notEqual(bare.material,original);assert.equal(bare.material.color.getHex(),0xb7bdc4);assert.equal(bare.material.metalness,0);
 assert.equal(vertexColored.material,original);assert.equal(painted.material,authored);assert.equal(authored.color.getHex(),0xff0000);
});
