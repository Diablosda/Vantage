// Move an imported model's local pivot without changing its object, path, or direction.
export function calibrateOrigin(project,o,role=o.role){
 if(!o.modelSource)return;
 let min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
 for(const part of o.parts||[]){const m=part.matrix;for(const v of part.vertices||[]){const p=[0,1,2].map(i=>m[i]*v[0]+m[i+4]*v[1]+m[i+8]*v[2]+m[i+12]);for(let i=0;i<3;i++){min[i]=Math.min(min[i],p[i]);max[i]=Math.max(max[i],p[i]);}}}
 if(!Number.isFinite(min[0]))throw Error('模型没有可校准的网格');
 const delta=[(min[0]+max[0])/2,(min[1]+max[1])/2,role==='ACTOR'?min[2]:(min[2]+max[2])/2];
 o.parts=o.parts.map(p=>{const matrix=[...p.matrix];for(let i=0;i<3;i++)matrix[i+12]-=delta[i];return {...p,matrix};});
 const yaw=o.modelSource.localYaw||0,c=Math.cos(yaw),s=Math.sin(yaw);o.modelSource.center=[o.modelSource.center[0]+c*delta[0]+s*delta[1],o.modelSource.center[1]-s*delta[0]+c*delta[1],o.modelSource.center[2]+delta[2]];
 for(const obj of project.objects)for(const shot of Object.values(obj.shots||{}))if(shot.focusTarget===o.id&&shot.focusLocal)shot.focusLocal=shot.focusLocal.map((v,i)=>v-delta[i]);
}
