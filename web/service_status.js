// UI compatibility follows API capabilities, not the product's patch version.
export function modernWorkflow(status){
 if(status?.app!=='previs-local')return false;
 if(status.apiVersion!==undefined)return status.apiVersion===1&&['save-directory','project-bundle','render-video'].every(c=>status.capabilities?.includes(c));
 const match=/^(\d+)\.(\d+)\.(\d+)$/.exec(status.version||'');
 if(!match)return false;
 const [major,minor,patch]=match.slice(1).map(Number);
 return major>2||major===2&&(minor>0||patch>=4);
}
