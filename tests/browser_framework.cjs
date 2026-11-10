const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
(async()=>{
 const server=spawn('python',['server.py','--port','8767'],{windowsHide:true});
 await new Promise((resolve,reject)=>{server.stdout.on('data',d=>{if(d.toString().includes('8767'))resolve();});server.on('error',reject);server.on('exit',code=>reject(Error('Test server exited '+code)));});
 const browser=await chromium.launch({headless:true,executablePath:process.env.PREVIS_CHROMIUM,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.stack));
  await page.route('**/app.js',async route=>{const response=await route.fetch();await route.fulfill({response,body:(await response.text())+'\nglobalThis.__test={get project(){return project},view,loadProject,openShot,shotData,select,setTime,blank};'});});
  await page.goto(process.env.PREVIS_URL||'http://127.0.0.1:8767/');await page.waitForFunction(()=>window.__test);
  await page.evaluate(()=>{__test.loadProject(__test.blank());__test.select(__test.project.activeCamera);});
  assert.equal(await page.locator('[data-field="viewMode"]').count(),0);assert.equal(await page.locator('[data-vector="position"]').count(),0);assert.equal(await page.locator('[data-field="lens"]').count(),1);
  await page.evaluate(async()=>{
   const {migrate,setDwell}=await import('/segments.js'),t=__test,p=structuredClone(t.project);
   for(const id of ['A','B'])p.objects.push({id,name:id,role:'PROP',position:[0,id==='A'?0:3,.5],rotation:[0,0,0],scale:[1,1,1],parts:[{shape:'BOX',matrix:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}],nodes:[0,1,2].map(i=>({position:[i*2,id==='A'?0:3,.5],time:i*2,dwell:0,radius:0})),angles:[],lenses:[],rolls:[],orientation:'FIXED'});
   migrate(p);const a=p.objects.find(o=>o.id==='A');setDwell(a,a.nodes[1],2);p.settings.duration=6;t.loadProject(p);
  });
  await page.locator('.dwell[data-track="A"]').click({button:'right'});await page.getByRole('button',{name:'设置镜头',exact:true}).click();
  assert.equal(await page.locator('#inheritPrevious').inputValue(),'no');await page.getByRole('button',{name:'自由模式',exact:true}).click();
  const shot=k=>page.locator(`[data-shot="${k}"]`);
  assert.equal(await shot('mode').inputValue(),'FREE');await shot('motion').selectOption('ORBIT');await shot('radius').fill('5');await shot('orbitAngle').fill('90');await shot('lensEnd').fill('80');await shot('lensEnd').press('Tab');
  assert.equal(await page.locator('#editLayer').inputValue(),'CAMERA');
  await page.locator('#dragShotStart').click();await page.evaluate(()=>__test.view.focus(__test.project.activeCamera));await page.locator('#viewport').scrollIntoViewIfNeeded();
  const drag=await page.evaluate(()=>{const v=__test.view,r=v.renderer.domElement.getBoundingClientRect(),p=v.handle.position.clone().add({x:.55,y:0,z:0});p.project(v.camera);return {x:r.x+(p.x+1)*r.width/2,y:r.y+(1-p.y)*r.height/2,before:[...__test.shotData().cfg.start.position]};});
  await page.mouse.move(drag.x,drag.y);await page.mouse.down();await page.mouse.move(drag.x+80,drag.y,{steps:12});await page.mouse.up();
  assert.notDeepEqual(await page.evaluate(()=>__test.shotData().cfg.start.position),drag.before,'native drag updates current shot');
  await page.getByRole('button',{name:'编辑相机路径',exact:true}).click();await page.getByRole('button',{name:'数值加点',exact:true}).click();await page.locator('#dialogActions').getByRole('button',{name:'添加',exact:true}).click();
  assert.equal(await page.evaluate(()=>Object.values(__test.project.objects.find(o=>o.role==='CAMERA').shots)[0].freeMotion.nodes.length),2);
  await page.getByRole('button',{name:'清空',exact:true}).click();await page.locator('[data-action="selectCamera"]').first().click();
  const state=()=>page.evaluate(()=>({cfg:structuredClone(__test.shotData().cfg),pos:__test.view.roots.get(__test.project.activeCamera).position.toArray(),warning:__test.view.warning}));
  assert.equal((await state()).warning,'');
  const before=await page.evaluate(()=>{__test.setTime(3);return {p:JSON.stringify(__test.project),pos:__test.view.roots.get('B').position.toArray()};});
  assert.deepEqual(before.pos,[3,3,.5]);await page.locator('#editLayer').selectOption('OBJECT');await page.locator('#editLayer').selectOption('CAMERA');assert.equal(await page.evaluate(()=>JSON.stringify(__test.project)),before.p);
  await page.evaluate(()=>__test.select('A'));assert.equal(await page.evaluate(()=>!!__test.view.control.object),false);assert.equal(await page.locator('[data-field="nodeDwell"]').count(),0);
  await page.locator('#editLayer').selectOption('OBJECT');await page.locator('.segment[data-track="B"][data-edge-id="B-segment-1"]').click({button:'right'});await page.getByRole('button',{name:'设置镜头',exact:true}).click();await page.locator('#inheritPrevious').selectOption('yes');await page.getByRole('button',{name:'跟踪模式',exact:true}).click();
  assert.equal(await shot('mode').inputValue(),'TRACK');assert.equal((await state()).cfg.lens,80);assert.equal(await page.evaluate(()=>Object.keys(__test.project.objects.find(o=>o.role==='CAMERA').shots).length),1);
  for(let i=0;i<4;i++){await shot('mode').selectOption(i%2?'TRACK':'FREE');await shot('motion').selectOption(i%2?'ORBIT':'DIAGONAL');}
  await shot('focusTarget').selectOption('A');assert.equal((await state()).warning,'');
  await page.locator('#previewShot').click();await page.waitForTimeout(500);assert.equal((await state()).warning,'');
  assert.deepEqual(await page.evaluate(()=>[__test.view.renderer,__test.view.previewRenderer].map(r=>r.getContext().isContextLost())),[false,false]);
  if(process.env.PREVIS_SCREENSHOT)await page.screenshot({path:process.env.PREVIS_SCREENSHOT});
  const saved=await page.evaluate(()=>JSON.stringify(__test.project));await page.locator('#openFile').setInputFiles({name:'framework.previs',mimeType:'application/json',buffer:Buffer.from(saved)});await page.waitForFunction(()=>document.querySelector('#dirty').textContent==='已载入');
  assert.deepEqual(await page.evaluate(()=>__test.project),JSON.parse(saved));assert.deepEqual(errors,[]);console.log('Framework browser checks passed');
 }finally{await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
