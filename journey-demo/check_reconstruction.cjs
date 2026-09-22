// Check the actual Spark-served artifact without downloading large exports.
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
async function main(){
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1120},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]||'http://127.0.0.1:8767/',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>window.journeyState&&!window.journeyState().loading,{timeout:120000});
  const checks=[];
  for(const id of ['sai-kung-boat','coastal-trail','yi-o-harvest']){
   await page.locator(`[data-scene="${id}"]`).click();
   await page.waitForFunction(id=>window.journeyState().scene===id&&!window.journeyState().loading,id,{timeout:120000});
   const state=await page.evaluate(()=>window.journeyState());
   assert.equal(state.vertices,32400);assert.equal(state.triangles,64052);assert(state.depthSpan>.05);
   await page.waitForFunction(f=>window.journeyState().frame!==f,state.frame,{timeout:10000});
   await page.locator('#motion').click();
   const paused=await page.evaluate(()=>window.journeyState());assert.equal(paused.playing,false);
   await page.waitForTimeout(180);assert.equal((await page.evaluate(()=>window.journeyState())).time,paused.time);
   await page.locator('#scale').evaluate(el=>{el.value='0.8';el.dispatchEvent(new Event('input',{bubbles:true}))});
   assert.equal((await page.evaluate(()=>window.journeyState())).scale,.8);
   await page.locator('#reset').click();
   assert.equal((await page.evaluate(()=>window.journeyState())).scale,1);
   const box=await page.locator('#canvas').boundingBox();const before=(await page.evaluate(()=>window.journeyState())).camera;
   await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();
   await page.mouse.move(box.x+box.width*.5+70,box.y+box.height*.5+20,{steps:12});await page.mouse.up();
   const after=(await page.evaluate(()=>window.journeyState())).camera;
   assert(Math.abs(before[0]-after[0])>.01);
   await page.mouse.wheel(0,100);await page.waitForTimeout(200);
   assert.notDeepEqual((await page.evaluate(()=>window.journeyState())).camera,after);
   await page.locator('#inspect').click();assert((await page.evaluate(()=>window.journeyState())).inspecting);
   if(id==='coastal-trail'&&process.argv[3])await page.screenshot({path:process.argv[3]+'/geometry.jpg',quality:70});
   await page.locator('#inspect').click();await page.locator('#reset').click();
   if(process.argv[3])await page.screenshot({path:process.argv[3]+'/'+id+'.jpg',fullPage:true,quality:70});
   await page.locator('#motion').click();
   checks.push({scene:id,vertices:state.vertices,triangles:state.triangles,depth_span:state.depthSpan,animation:true,rotate_zoom_scale:true});
  }
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if(process.argv[3])await page.screenshot({path:process.argv[3]+'/mobile.jpg',fullPage:true,quality:70});
  const manifest=await (await page.request.get(new URL('manifest.json',page.url()).href)).json();
  assert.equal(manifest.stepfun_calls,0);assert.equal(manifest.omniverse_complete,true);
  for(const path of [manifest.usd_bundle,...manifest.scenes.map(s=>s.glb)]){
   const response=await page.request.head(new URL(path,page.url()).href);assert(response.ok());assert(Number(response.headers()['content-length'])>1000);
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,checks,mobile_overflow:false,browser_errors:errors,downloads_exist:true},null,2));
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
