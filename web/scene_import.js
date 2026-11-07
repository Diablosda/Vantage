// The source coordinates and dimensions are converted exactly once on import.
export function scaleSceneObjects(objects,k){
 if(!Number.isFinite(k)||k<.001||k>1000)throw Error('导入比例无效');
 for(const o of objects){o.position=o.position.map(v=>v*k);o.scale=o.scale.map(v=>v*k);if(o.sceneSource)o.sceneSource.unitScale=k;}
 return objects;
}

export function initialSceneCamera(min,max,grid){
 const target=[(min[0]+max[0])/2,(min[1]+max[1])/2,min[2]+Math.max(1.5,grid*2)];
 const distance=Math.max(4,Math.min(10,grid*6));
 return {target,position:[target[0]+distance,target[1]-distance,target[2]+distance*.6]};
}

// Scale the background as one assembly around a stable world-space pivot.
export function setSceneScale(project, value, pivot){
 if(!Number.isFinite(value)||value<.001||value>1000)throw Error('场景比例须在 0.001 到 1000 之间');
 const old=project.settings.sceneScale??1;
 if(!Number.isFinite(old)||old<=0)throw Error('已保存的场景比例无效');
 const anchor=project.settings.sceneScalePivot??pivot;
 if(!Array.isArray(anchor)||anchor.length!==3||anchor.some(n=>!Number.isFinite(n)))throw Error('场景缩放中心无效');
 const objects=project.objects.filter(o=>o.role==='ENV'||o.sceneSource?.kind==='LIGHT');
 if(!objects.length)throw Error('请先导入或创建背景场景');
 const factor=value/old,position=p=>p.map((n,i)=>anchor[i]+(n-anchor[i])*factor),size=p=>p.map(n=>n*factor);
 for(const o of objects){
  o.position=position(o.position);o.scale=size(o.scale);
  if(o.initialState)o.initialState={...o.initialState,position:position(o.initialState.position),scale:size(o.initialState.scale)};
 }
 project.settings.sceneScalePivot=[...anchor];project.settings.sceneScale=value;
}
