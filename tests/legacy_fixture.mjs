// Build saved V1.1/V1.2 configurations for compatibility regression tests.
import {newShot,edges,Evaluator,captureStart} from '../web/segments.js';
export function legacyShot(p,c,o,sid){
 const ss=edges(o),i=ss.findIndex(s=>s.id===sid),ev=new Evaluator(p),previous=i>0?c.shots?.[ss[i-1].id]:null;
 const cfg=previous?structuredClone(previous):newShot(p,c,o,sid);
 delete cfg.controlVersion;delete cfg.orbitAngle;delete cfg.azimuth;
 cfg.inherit=i>0;cfg.start=captureStart(ev.previous(c,o,i));
 if(!previous){const f=ev.focus(o,cfg.focusLocal,ss[i].startTime);cfg.radius=Math.max(.1,Math.hypot(...cfg.start.position.map((v,j)=>v-f[j])));}
 return cfg;
}
