const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');const path=require('node:path');const os=require('node:os');const fs=require('node:fs');const assert=require('node:assert/strict');
(async()=>{const root=path.resolve(__dirname,'..'),port=18947;const server=spawn(process.env.PYTHON||'python',['-B','server.py','--port',String(port)],{cwd:root,windowsHide:true,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});let browser;
try{
 await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('error',reject);server.once('exit',code=>reject(Error('server exited '+code)));setTimeout(()=>reject(Error('server startup timeout')),10000).unref();});
 browser=await chromium.launch({headless:true,...(process.env.PREVIS_CHROMIUM?{executablePath:process.env.PREVIS_CHROMIUM}:{}),args:['--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1366,height:768}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/app.js',async route=>{const r=await route.fetch();await route.fulfill({response:r,body:(await r.text())+'\nglobalThis.__test={get project(){return project},loadProject,closeModal,objectMenu,openShot,actions,setTime,mannequinParts};'});});
 await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.__test);await page.evaluate(()=>{
 const p=structuredClone(__test.project);const part=(shape,size,pos)=>({shape,matrix:[size[0],0,0,0,0,size[1],0,0,0,0,size[2],0,...pos,1]});
 const obj=(id,role,parts,position)=>({id,name:id,role,parts,position,rotation:[0,0,0],scale:[1,1,1],nodes:[],angles:[],lenses:[],rolls:[],orientation:'FIXED',offset:[0,0,0]});
 p.objects.push(obj('floor','ENV',[part('BOX',[20,20,.2],[0,0,-.1])],[0,0,0]),obj('sphere','PROP',[part('SPHERE',[2,2,2],[0,0,0])],[2,3,0]));
 const actor=obj('focus-box','ACTOR',__test.mannequinParts(),[0,0,0]);actor.nodes=[{id:'n1',position:[0,0,0],time:0,dwell:0,radius:0},{id:'n2',position:[1,0,0],time:2,dwell:0,radius:0}];p.objects.push(actor);__test.closeModal();__test.loadProject(p);__test.objectMenu('sphere',300,200);
 });
 await page.getByRole('button',{name:'接触地面',exact:true}).click();assert.equal(await page.evaluate(()=>__test.project.objects.find(o=>o.id==='sphere').position[2]),1);
 await page.locator('#undoBtn').click();assert.equal(await page.evaluate(()=>__test.project.objects.find(o=>o.id==='sphere').position[2]),0);await page.locator('#redoBtn').click();assert.equal(await page.evaluate(()=>__test.project.objects.find(o=>o.id==='sphere').position[2]),1);
 await page.evaluate(async()=>{const {edges}=await import('/segments.js');const p=__test.project,o=p.objects.find(o=>o.id==='focus-box');__test.openShot(o.id,edges(o)[0].id,p.activeCamera,'TRACK');});
 await page.getByRole('button',{name:'放大窗口',exact:true}).click();const dialog=page.locator('.focus-picker-dialog');await dialog.waitFor({state:'visible'});
 const r=await dialog.boundingBox();assert(r.width>900&&r.height>650);await page.getByRole('button',{name:'放大焦点模型',exact:true}).click();await page.getByRole('button',{name:'放大焦点模型',exact:true}).click();
 const canvas=dialog.locator('canvas'),b=await canvas.boundingBox();await canvas.click({position:{x:b.width*.5,y:b.height*.55}});
 assert(await dialog.isVisible());const focus=await page.evaluate(()=>Object.values(__test.project.objects.find(o=>o.role==='CAMERA').shots)[0].focusLocal);assert(focus.every(Number.isFinite));assert(focus.some(n=>Math.abs(n)>.01));
 const before=await page.evaluate(()=>__test.project.objects.find(o=>o.id==='focus-box').position);await page.keyboard.press('ArrowUp');assert.deepEqual(await page.evaluate(()=>__test.project.objects.find(o=>o.id==='focus-box').position),before);
 const dir=process.env.VANTAGE_QA_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'vantage-qa-'));fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,'focus-expanded.png')});
 await page.keyboard.press('Escape');assert.equal(await page.locator('.focus-picker-dialog').count(),0);assert(await page.locator('#focusPicker canvas').isVisible());await page.getByRole('button',{name:'复位',exact:true}).click();
 await page.setViewportSize({width:1920,height:1080});await page.getByRole('button',{name:'放大窗口',exact:true}).click();await page.getByRole('button',{name:'收起窗口',exact:true}).click();assert.equal(await page.locator('.focus-picker-dialog').count(),0);
 assert.deepEqual(errors,[]);console.log('PASS: ground menu, undo/redo, enlarged focus, zoom, pick, Escape, keyboard isolation, 1366/1920 layouts; screenshot '+path.join(dir,'focus-expanded.png'));
}finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1});
