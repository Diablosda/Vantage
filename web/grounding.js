import {translateObjectAndPath,canColor} from './object_tools.js';

export function canGround(o){return canColor(o)&&(o.parts||[]).every(p=>['BOX','SPHERE','CYLINDER','CONE','MESH'].includes(p.shape));}
// Support along world Z, after part transform, object scale and evaluated rotation.
// Analytic primitive extents avoid the gaps caused by transforming a bounding cube.
export function lowestPoint(o,pose){
 const [x,y,z,w]=pose.quaternion,s=o.scale;
 const row=[2*(x*z-y*w)*s[0],2*(y*z+x*w)*s[1],(1-2*(x*x+y*y))*s[2]];
 let bottom=Infinity;
 for(const p of o.parts||[]){const m=p.matrix;
  const a=[0,1,2].map(i=>row.reduce((v,n,j)=>v+n*m[i*4+j],0));
  const origin=pose.position[2]+row.reduce((v,n,j)=>v+n*m[12+j],0);
  let extent;
  if(p.shape==='BOX')extent=-a.reduce((v,n)=>v+Math.abs(n),0)/2;
  else if(p.shape==='SPHERE')extent=-Math.hypot(...a)/2;
  else if(p.shape==='CYLINDER')extent=-(Math.hypot(a[0],a[1])+Math.abs(a[2]))/2;
  else if(p.shape==='CONE'){const radius=Math.hypot(a[0],a[1])/2;extent=Math.min(-radius-a[2]/2,-radius*(p.topRatio||0)+a[2]/2);}
  else if(p.shape==='MESH')extent=(p.vertices||[]).reduce((min,v)=>Math.min(min,v.reduce((sum,n,i)=>sum+n*a[i],0)),Infinity);
  else throw Error('该对象不支持接触地面');
  bottom=Math.min(bottom,origin+extent);
 }
 if(!Number.isFinite(bottom))throw Error('无法计算几何体底部');
 return bottom;
}
export function groundObject(o,pose,ground=0){
 if(!canGround(o))throw Error('请选择自建白模或几何体');
 if(o.follow)throw Error('请先解除对象跟随后再接触地面');
 if(o.locked)throw Error('对象已锁定，请先解锁');
 if(!Number.isFinite(ground))throw Error('地面高度无效');
 const delta=ground-lowestPoint(o,pose);
 if(Math.abs(delta)<1e-9)return 0;
 translateObjectAndPath(o,[0,0,delta]);return delta;
}
