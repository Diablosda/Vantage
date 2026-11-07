// The baseline is captured once and saved with the object, independent of undo.
export function rememberInitial(o){
 if(o.initialState)return;
 o.initialState={position:[...o.position],rotation:[...o.rotation],scale:[...o.scale],orientation:o.orientation||'FIXED',lens:o.lens,controlScale:o.controlScale,viewMode:o.viewMode,target:o.target,offset:[...(o.offset||[0,0,0])],follow:o.follow,roll:o.roll||0,rollEnabled:!!o.rollEnabled};
}
export function resetObject(o){
 rememberInitial(o);
 Object.assign(o,structuredClone(o.initialState));
 o.nodes=[];o.segments=[];o.shots={};o.angles=[];o.lenses=[];o.rolls=[];
}
