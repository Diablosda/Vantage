import * as THREE from './vendor/three/build/three.module.js';
// Screen-space ribbon: WebGL lineWidth is fixed to one pixel on many Windows GPUs.
export function pathMark(points,color=0x52d8ef){
 const positions=[],other=[],sides=[],indices=[];
 for(let i=1;i<points.length;i++){
  const a=points[i-1],b=points[i],base=positions.length/3;
  positions.push(...a,...a,...b,...b);other.push(...b,...b,...a,...a);sides.push(-1,1,1,-1);indices.push(base,base+1,base+2,base+1,base+3,base+2);
 }
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('other',new THREE.Float32BufferAttribute(other,3));geometry.setAttribute('side',new THREE.Float32BufferAttribute(sides,1));geometry.setIndex(indices);
 const material=new THREE.ShaderMaterial({uniforms:{resolution:{value:new THREE.Vector2(1,1)},color:{value:new THREE.Color(color)}},depthTest:false,depthWrite:false,side:THREE.DoubleSide,
 vertexShader:`attribute vec3 other;attribute float side;uniform vec2 resolution;
 void main(){vec4 a=projectionMatrix*modelViewMatrix*vec4(position,1.0);vec4 b=projectionMatrix*modelViewMatrix*vec4(other,1.0);
 if(a.w<=0.00001||b.w<=0.00001){gl_Position=vec4(2.0,2.0,2.0,1.0);return;}
 vec2 d=(b.xy/b.w-a.xy/a.w)*resolution;float len=length(d);vec2 n=len>0.00001?vec2(-d.y,d.x)/len:vec2(0.0);
 a.xy+=n*side*4.0/resolution*a.w;gl_Position=a;}`,
 fragmentShader:`uniform vec3 color;void main(){gl_FragColor=vec4(color,1.0);}`});
 const mesh=new THREE.Mesh(geometry,material);mesh.renderOrder=4;mesh.frustumCulled=false;mesh.raycast=()=>{};mesh.onBeforeRender=renderer=>renderer.getSize(material.uniforms.resolution.value);return mesh;
}
