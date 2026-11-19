// Keyboard movement stays on the XY ground plane and follows screen orientation.
export function gridMove(key, step, screenRight){
 if(!Number.isFinite(step)||step<=0||!Array.isArray(screenRight)||!screenRight.slice(0,2).every(Number.isFinite))throw Error('网格步长或视图方向无效');
 const [x,y]=screenRight;let right;
 if(Math.max(Math.abs(x),Math.abs(y))<1e-8)right=[1,0];
 else right=Math.abs(x)>=Math.abs(y)?[Math.sign(x),0]:[0,Math.sign(y)];
 const forward=[-right[1],right[0]], map={ArrowRight:right,ArrowLeft:right.map(v=>-v),ArrowUp:forward,ArrowDown:forward.map(v=>-v)};
 const dir=map[key];return dir?[(dir[0]*step)||0,(dir[1]*step)||0,0]:null;
}
export function translateObjectAndPath(o, delta){
 const moved=p=>p.map((n,i)=>n+delta[i]);
 const positions=[o.position,...(o.nodes||[]).map(n=>n.position)].map(moved);
 if(positions.some(p=>p.some(n=>!Number.isFinite(n)||Math.abs(n)>1e6)))throw Error('移动超出有效坐标范围');
 o.position=positions[0];(o.nodes||[]).forEach((n,i)=>n.position=positions[i+1]);
}
export function canColor(o){return !!o&&['ACTOR','PROP'].includes(o.role)&&!o.modelSource&&!o.sceneSource&&!!o.parts?.length;}

export function canGhostModel(o){return o?.role==='ACTOR'||o?.role==='PROP';}
export function isEditorGhost(o){return canGhostModel(o)&&o.hidden===true&&o.ghostInEditor===true;}
export function toggleVisibility(o){
 o.hidden=!o.hidden;
 if(o.hidden&&canGhostModel(o))o.ghostInEditor=true;
 else delete o.ghostInEditor;
}
