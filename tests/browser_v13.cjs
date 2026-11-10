// Optional real-browser regression. Set PLAYWRIGHT_MODULE, PREVIS_CHROMIUM and (optionally) PREVIS_URL.
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PREVIS_CHROMIUM||undefined,args:['--enable-unsafe-swiftshader']});
 try{
 const page=await browser.newPage({viewport:{width:1600,height:1100}});const errors=[];
 page.on('pageerror',e=>errors.push(e.stack));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/app.js',async route=>{const response=await route.fetch();await route.fulfill({response,body:(await response.text())+'\nglobalThis.__test={get project(){return project},view,loadProject,openShot,shotData,select};'});});
 await page.goto(process.env.PREVIS_URL||'http://127.0.0.1:8765/');await page.waitForFunction(()=>window.__test);
 await page.evaluate(async()=>{
  const {migrate,edges,newShot}=await import('/segments.js');const p=structuredClone(__test.project),c=p.objects[0],t=p.objects[1];
  const o={id:'test-actor',name:'测试白模',role:'PROP',position:[0,0,.5],rotation:[0,0,0],scale:[1,1,1],parts:[{shape:'BOX',matrix:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}],nodes:[[0,0,.5],[2,0,.5],[4,1,.5]].map((position,i)=>({position,time:i*2,dwell:0,radius:.5})),angles:[],lenses:[],rolls:[],orientation:'FIXED'};
  p.objects.push(o);t.follow=o.id;t.offset=[0,0,.5];c.position=[3,-4,3];p.settings.duration=4;p.settings.snap=false;p.name='临时交互回归';migrate(p);c.shots={};for(const s of edges(o))c.shots[s.id]=newShot(p,c,o,s.id);
  __test.loadProject(p);__test.openShot(o.id,o.segments[0].id,c.id);
 });
 const shot=k=>page.locator(`[data-shot="${k}"]`);
 const state=()=>page.evaluate(()=>({cfg:structuredClone(__test.shotData().cfg),scroll:document.querySelector('#inspector').scrollTop,pos:__test.view.roots.get(__test.project.activeCamera).position.toArray(),warning:__test.view.warning,contexts:[__test.view.renderer,__test.view.previewRenderer].map(r=>r.getContext().isContextLost())}));
 await shot('motion').selectOption('ORBIT');
 // Multi-digit typing must keep input focus and sidebar scroll; live camera must update.
 await shot('lens').scrollIntoViewIfNeeded();await shot('lens').fill('');const initial=await state();await shot('lens').pressSequentially('6');const one=await state();await shot('lens').pressSequentially('5');const two=await state();assert.equal(two.cfg.lens,65);assert.equal(await shot('lens').inputValue(),'65');assert.equal(one.scroll,initial.scroll);assert.equal(two.scroll,initial.scroll);assert.deepEqual(two.pos,initial.pos);
 await shot('lens').fill('');await shot('lens').press('Tab');assert.equal((await state()).cfg.lens,65);await shot('lens').fill('50');await shot('lens').press('Tab');assert.equal((await state()).cfg.lens,50);
 for(const [key,value] of [['azimuth','90'],['elevation','30'],['radius','5'],['orbitAngle','90']]){await shot(key).fill(value);await shot(key).press('Tab');}
 let s=await state();assert.ok(Math.abs(s.pos[0])<1e-6);assert.ok(Math.abs(s.pos[1]-5)<1e-6);assert.ok(Math.abs(s.pos[2]-(1+5*Math.tan(Math.PI/6)))<1e-6);
 // Re-pick focus through actual focus canvas.
 await page.locator('#focusPicker canvas').scrollIntoViewIfNeeded();const box=await page.locator('#focusPicker canvas').boundingBox();await page.mouse.click(box.x+box.width/2,box.y+box.height/2);assert.deepEqual((await state()).cfg.start.position,s.cfg.start.position);assert.notDeepEqual((await state()).cfg.focusLocal,s.cfg.focusLocal,'surface click must actually change focus');
 // Native TransformControls drag along projected X axis, no test-injected move events.
 await page.locator('#dragShotStart').click();await page.locator('#viewport').scrollIntoViewIfNeeded();
 const drag=await page.evaluate(()=>{const v=__test.view,c=v.camera,r=v.renderer.domElement.getBoundingClientRect(),p=v.handle.position.clone(),project=w=>{w.project(c);return {x:r.x+(w.x+1)*r.width/2,y:r.y+(1-w.y)*r.height/2};};return {origin:project(p.clone()),x:project(p.clone().add({x:.55,y:0,z:0}))};});
 const beforeDrag=await state();await page.mouse.move(drag.x.x,drag.x.y);await page.mouse.down();await page.mouse.move(drag.x.x+90,drag.x.y,{steps:12});await page.mouse.up();
 const afterDrag=await state();assert.notDeepEqual(afterDrag.cfg.start.position,beforeDrag.cfg.start.position,'actual mouse drag must change the saved start');assert.deepEqual(afterDrag.cfg.focusLocal,beforeDrag.cfg.focusLocal);
 // Repeated mode switches, pole/coincident edits and preview rendering.
 for(let i=0;i<12;i++){
  await shot('motion').selectOption(i%2?'ORBIT':'TRANSLATE');
  await shot('start-0').fill(String(i%4));await shot('start-1').fill(String(-i%3));await shot('start-2').fill(String(i%5+1));await shot('lens').fill(String(35+i));await shot('lens').press('Tab');const sample=await state();assert.equal(sample.cfg.lens,35+i,JSON.stringify(sample));assert.equal(sample.cfg.start.position[1],(-i%3)||0,JSON.stringify(sample));
 }
 await shot('motion').selectOption('ORBIT');await shot('focus-0').fill('0');await shot('focus-1').fill('0');await shot('focus-2').fill('0');
 for(const [x,y,z] of [[0,0,5],[0,0,-5],[0,0,.5]]){for(const [key,value]of [['start-0',x],['start-1',y],['start-2',z]])await shot(key).fill(String(value));await shot('start-2').press('Tab');assert.deepEqual((await state()).contexts,[false,false]);}
 await shot('start-0').fill('3');await shot('start-1').fill('-4');await shot('start-2').fill('3');await shot('start-2').press('Tab');
 await page.locator('#previewShot').click();await page.waitForTimeout(2300);
 // Switch segments; copying is one-time, and returning to either segment preserves its own state.
 const first=await state();
 await page.evaluate(()=>{const t=__test,p=t.project,o=p.objects.find(o=>o.id==='test-actor');t.openShot(o.id,o.segments[1].id,p.activeCamera);});
 assert.equal((await state()).cfg.lens,50);assert.equal((await state()).cfg.motion,'TRANSLATE');
 await page.locator('#inheritShot').click();const copied=await state();assert.equal(copied.cfg.lens,46);assert.equal(copied.cfg.inherit,false);assert.equal(copied.cfg.motion,'ORBIT');
 await shot('start-0').fill('15');await shot('start-0').press('Tab');
 await page.evaluate(()=>{const t=__test,p=t.project,o=p.objects.find(o=>o.id==='test-actor');t.openShot(o.id,o.segments[0].id,p.activeCamera);});
 assert.deepEqual((await state()).cfg,first.cfg);await shot('lens').fill('60');await shot('lens').press('Tab');
 await page.evaluate(()=>{const t=__test,p=t.project,o=p.objects.find(o=>o.id==='test-actor');t.openShot(o.id,o.segments[1].id,p.activeCamera);});
 assert.equal((await state()).cfg.lens,46);assert.equal((await state()).cfg.start.position[0],15);
 // Round-trip through the actual file input and validation endpoint, in this isolated context.
 const saved=await page.evaluate(()=>JSON.stringify(__test.project));
 await page.locator('#openFile').setInputFiles({name:'regression.previs',mimeType:'application/json',buffer:Buffer.from(saved)});
 await page.waitForFunction(()=>document.querySelector('#dirty').textContent==='已载入');assert.deepEqual(await page.evaluate(()=>__test.project),JSON.parse(saved));
 await page.evaluate(()=>{const t=__test,p=t.project,o=p.objects.find(o=>o.id==='test-actor'),c=p.objects.find(o=>o.role==='CAMERA');const cfg=c.shots[o.segments[0].id];delete cfg.controlVersion;cfg.orbitFree=true;cfg.radius=Math.hypot(...cfg.start.position);t.openShot(o.id,o.segments[0].id,c.id);});
 assert.equal(await page.locator('#convertShot').count(),1);const legacy=await state();await page.locator('#convertShot').click();assert.equal((await state()).cfg.controlVersion,3);assert.deepEqual((await state()).cfg.start.position,legacy.cfg.start.position);
 await page.locator('[data-action="selectCamera"]').click();assert.equal(await page.evaluate(()=>__test.view.startEdit?.camera),await page.evaluate(()=>__test.project.activeCamera));await page.locator('[data-shot="azimuth"]').scrollIntoViewIfNeeded();
 await page.screenshot({path:require('node:path').join(__dirname,'../.runtime/V1.3交互验证.png')});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:['multi-digit input scroll/focus','empty input rejection','parameter position sync','focus pick keeps start','native gizmo drag','12 mode-switch/edit cycles','pole/coincident rendering','shot playback','independent segments','snapshot inheritance','file reopen','legacy conversion'],final:await state(),errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
