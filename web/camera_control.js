// A display handle encodes focal length by radius; the aim anchor can still follow a subject.
export const MIN_REACH=.8;
export const clampLens=x=>Math.max(1,Math.min(1000,x));
export function controlScale(distance,lens){return Math.max(.01,(distance-MIN_REACH)/clampLens(lens));}
export function controlReach(lens,scale){return MIN_REACH+clampLens(lens)*scale;}
export function controlLens(distance,scale){return clampLens((distance-MIN_REACH)/scale);}
export function controlPoint(camera,aim,lens,scale,fallback=[0,1,0]){const d=aim.map((v,i)=>v-camera[i]),length=Math.hypot(...d),direction=length>1e-6?d.map(v=>v/length):fallback;return camera.map((v,i)=>v+direction[i]*controlReach(lens,scale));}
