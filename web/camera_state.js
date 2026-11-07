// Camera coordinates are authoritative; orbit parameters are derived, never a second controller.
export const POSITION_EPS = 1e-7;
export const SAFE_RADIUS = .001; // metres
export const MAX_VALUE = 1e6;
export function numberInput(raw, min=-MAX_VALUE, max=MAX_VALUE){
 if(typeof raw!=='number'&&(typeof raw!=='string'||!raw.trim()))throw Error('请输入有效数字，空值不会修改当前状态');
 const value=Number(raw);
 if(!Number.isFinite(value)||value<min||value>max)throw Error(`请输入 ${min} 到 ${max} 之间的有效数字`);
 return value;
}
export function finiteVector(v,size=3){return Array.isArray(v)&&v.length===size&&v.every(Number.isFinite);}
export function orbitParameters(position,focus,lastAzimuth=0){
 if(!finiteVector(position)||!finiteVector(focus))throw Error('相机或焦点坐标无效');
 const [dx,dy,dz]=position.map((v,i)=>v-focus[i]),radius=Math.hypot(dx,dy);
 const polar=radius<=POSITION_EPS,coincident=polar&&Math.abs(dz)<=POSITION_EPS;
 const azimuth=polar?lastAzimuth:((Math.atan2(dy,dx)*180/Math.PI)%360+360)%360;
 const actualElevation=Math.atan2(dz,radius)*180/Math.PI;
 return {radius,azimuth,elevation:Math.max(-89.9,Math.min(89.9,actualElevation)),actualElevation,dz,polar,coincident};
}
export function orbitPosition(position,focus,key,raw,lastAzimuth=0){
 const p=orbitParameters(position,focus,lastAzimuth),value=numberInput(raw);
 let r=p.radius,phi=p.azimuth,dz=p.dz;
 if(key==='azimuth')phi=(value%360+360)%360;
 else if(key==='elevation'){if(value< -89.9||value>89.9)throw Error('仰角范围为 -89.9° 到 89.9°');}
 else if(key==='radius'){if(value<0)throw Error('水平半径不能为负数');r=value;}
 else throw Error('未知环绕参数');
 // An explicit zero radius is allowed. Editing away from a pole uses a 1 mm radius.
 if(p.polar&&!(key==='radius'&&value===0))r=Math.max(SAFE_RADIUS,r);
 if(key==='elevation')dz=r*Math.tan(value*Math.PI/180);
 const angle=phi*Math.PI/180,next=[focus[0]+r*Math.cos(angle),focus[1]+r*Math.sin(angle),focus[2]+dz];
 next.forEach(v=>numberInput(v));return next;
}
export function validCameraState(state){
 if(!finiteVector(state.position)||state.position.some(v=>Math.abs(v)>MAX_VALUE)||state.focus&&!finiteVector(state.focus))throw Error('相机计算产生无效或过大的坐标，已保留上一有效画面');
 numberInput(state.lens,1,1000);
 const q=state.cameraRotation||state.quaternion;if(q&&(!finiteVector(q,4)||Math.abs(Math.hypot(...q)-1)>1e-4))throw Error('相机朝向无效，已保留上一有效画面');
 if(state.roll!==undefined&&!Number.isFinite(state.roll))throw Error('相机滚转角无效');
 return state;
}
