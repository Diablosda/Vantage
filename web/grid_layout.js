// Keep visible grid lines aligned to the exact snap interval.
export function gridLayout(bounds,step,ground=0){
 const spacing=Number(step);if(!Number.isFinite(spacing)||spacing<=0)throw Error('网格间距无效');
 const x0=bounds?.min?.[0]??-20,x1=bounds?.max?.[0]??20,y0=bounds?.min?.[1]??-20,y1=bounds?.max?.[1]??20;
 const cx=Math.round(((x0+x1)/2)/spacing)*spacing,cy=Math.round(((y0+y1)/2)/spacing)*spacing;
 const radius=Math.max(20,Math.abs(x0-cx),Math.abs(x1-cx),Math.abs(y0-cy),Math.abs(y1-cy))+spacing*5;
 const stride=Math.max(1,Math.ceil(radius*2/spacing/2048)),lineStep=spacing*stride,divisions=Math.ceil(radius/lineStep)*2;
 return {center:[cx,cy,ground+Math.min(.2,spacing*.2)],size:divisions*lineStep,divisions,lineStep,stride};
}
