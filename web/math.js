export const EPS=1e-7;
export const add=(a,b)=>a.map((x,i)=>x+b[i]);
export const sub=(a,b)=>a.map((x,i)=>x-b[i]);
export const mul=(a,s)=>a.map(x=>x*s);
export const length=a=>Math.hypot(...a);
export const distance=(a,b)=>length(sub(a,b));
export const unit=a=>length(a)>EPS?mul(a,1/length(a)):[0,0,0];
export const lerp=(a,b,t)=>add(a,mul(sub(b,a),t));
export function ease(t,mode){t=Math.max(0,Math.min(1,t));return mode==='IN'?t*t:mode==='OUT'?1-(1-t)**2:mode==='IN_OUT'?t*t*(3-2*t):t;}
export function node(position,time=0){return {position:[...position],time,dwell:0,exact:false,radius:.5,easing:'LINEAR'};}
export function validateNodes(nodes,duration=Infinity){const errors=[];nodes.forEach((n,i)=>{if([...n.position,n.time,n.dwell,n.radius].some(x=>!Number.isFinite(x)))errors.push(`P${i} 含无效数值`);if(n.time<0||n.dwell<0||n.radius<0)errors.push(`P${i} 时间和圆角不能为负`);if(n.time+n.dwell>duration+EPS)errors.push(`P${i} 超出片段时长`);if(i){const p=nodes[i-1];if(n.time<=p.time+p.dwell+EPS)errors.push(`P${i} 到达必须晚于上一点离开`);if(n.position.filter((x,k)=>Math.abs(x-p.position[k])>EPS).length>1)errors.push(`P${i-1} → P${i} 必须为单轴线段`);}});return errors;}
export function orthogonalize(nodes,order='XYZ'){if(!nodes.length)return [];const out=[structuredClone(nodes[0])];for(const end of nodes.slice(1)){const start=out.at(-1),p=[...start.position],total=p.reduce((s,v,i)=>s+Math.abs(v-end.position[i]),0);if(total<EPS){out.push(structuredClone(end));continue;}let travelled=0;for(const axis of order){const i='XYZ'.indexOf(axis),d=Math.abs(p[i]-end.position[i]);if(d<EPS)continue;p[i]=end.position[i];travelled+=d;if(distance(p,end.position)<EPS)out.push(structuredClone(end));else out.push({...node(p,start.time+start.dwell+(end.time-start.time-start.dwell)*travelled/total),radius:end.radius,easing:end.easing});}}return out;}
const bezier=(a,b,c,t)=>add(add(mul(a,(1-t)**2),mul(b,2*t*(1-t))),mul(c,t*t));
export class Arc{
 constructor(points){this.points=points;this.lengths=[0];points.slice(1).forEach((p,i)=>this.lengths.push(this.lengths.at(-1)+distance(points[i],p)));this.total=this.lengths.at(-1);}
 at(f){if(this.total<EPS)return [this.points[0],[0,0,0]];const d=Math.max(0,Math.min(1,f))*this.total;let i=0;while(i<this.points.length-2&&this.lengths[i+1]<=d)i++;const width=this.lengths[i+1]-this.lengths[i];return [lerp(this.points[i],this.points[i+1],width>EPS?(d-this.lengths[i])/width:0),unit(sub(this.points[i+1],this.points[i]))];}
}
export class Motion{
 constructor(nodes,smooth=false){this.nodes=nodes;const errors=validateNodes(nodes);if(errors.length)throw Error(errors.join('；'));const corners=new Map();if(smooth)for(let i=1;i<nodes.length-1;i++){const a=nodes[i-1].position,n=nodes[i],b=n.position,c=nodes[i+1].position,u=unit(sub(a,b)),v=unit(sub(c,b));if(n.exact||n.dwell||Math.abs(u.reduce((s,x,k)=>s+x*v[k],0))>.001)continue;const r=Math.min(n.radius,distance(a,b)*.49,distance(b,c)*.49);if(r>EPS)corners.set(i,[add(b,mul(u,r)),b,add(b,mul(v,r))]);}this.arcs=[];for(let i=0;i<nodes.length-1;i++){const points=[];if(corners.has(i))for(let j=0;j<=32;j++)points.push(bezier(...corners.get(i),.5+j/64));else points.push(nodes[i].position);if(corners.has(i+1))for(let j=0;j<=32;j++)points.push(bezier(...corners.get(i+1),j/64));else points.push(nodes[i+1].position);this.arcs.push(new Arc(points));}}
 at(t){const ns=this.nodes;if(!ns.length)throw Error('没有路径');let heading=[0,0,0];if(t<=ns[0].time+ns[0].dwell)return [ns[0].position,heading];for(let i=0;i<this.arcs.length;i++){const a=ns[i],b=ns[i+1],arc=this.arcs[i];if(t<=b.time){const [p,v]=arc.at(ease((t-a.time-a.dwell)/(b.time-a.time-a.dwell),b.easing));return [p,length(v)>EPS?v:heading];}const v=arc.at(1)[1];if(length(v)>EPS)heading=v;if(t<=b.time+b.dwell)return [b.position,heading];}return [ns.at(-1).position,heading];}
}
export function keyInterval(keys,t){const ks=[...keys].sort((a,b)=>a.time-b.time);if(!ks.length)return null;if(t<=ks[0].time)return [ks[0],ks[0],0];for(let i=1;i<ks.length;i++)if(t<=ks[i].time)return [ks[i-1],ks[i],ease((t-ks[i-1].time)/(ks[i].time-ks[i-1].time),ks[i].easing)];return [ks.at(-1),ks.at(-1),0];}
export function keyValue(keys,t,fallback){const k=keyInterval(keys,t);return k?k[0].value+(k[1].value-k[0].value)*k[2]:fallback;}
