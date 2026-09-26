const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const url=process.argv[2]||'http://127.0.0.1:8788/demo/';const out=process.argv[3]||'tmp/diverse-qa';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const results=[];
 try{for(const scene of (process.argv[4]?[process.argv[4]]:['coast','city'])){
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto(url+'?scene='+scene,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.travelSceneState,{timeout:120000});let state=await page.evaluate(()=>travelSceneState());assert.equal(state.error,null);assert.equal(state.loading,false);
  if(scene==='coast'){assert.equal(state.passengerCount,3);assert.equal(state.attachedToBoat,true);assert.equal(new Set(state.assets.filter(a=>a.startsWith('passenger-'))).size,3);}
  else{assert.equal(await page.locator('#canopy-control').isVisible(),false);assert(state.assets.includes('city/city-tram'));assert(state.assets.includes('city/city-buildings'));}
  const p0=state.subjectPosition;await page.waitForTimeout(400);assert.notDeepEqual((await page.evaluate(()=>travelSceneState())).subjectPosition,p0);
  await page.locator('#motion').click();const t=(await page.evaluate(()=>travelSceneState())).time;await page.waitForTimeout(250);assert.equal((await page.evaluate(()=>travelSceneState())).time,t);
  for(const preset of ['day','sunset','night']){await page.locator(`[data-preset="${preset}"]`).click();await page.waitForTimeout(300);state=await page.evaluate(()=>travelSceneState());assert.equal(state.preset,preset);if(preset==='night'){assert(state.stars>0);assert(state.lights.some(n=>n>0));}await page.screenshot({path:`${out}/${scene}-${preset}.png`});await page.locator('#canvas').screenshot({path:`${out}/${scene}-${preset}-canvas.png`});}
  await page.locator('#intensity').evaluate(el=>{el.value='1.4';el.dispatchEvent(new Event('input',{bubbles:true}))});assert.equal((await page.evaluate(()=>travelSceneState())).intensity,1.4);
  await page.locator('[data-preset="day"]').click();await page.locator('#intensity').evaluate(el=>{el.value='1';el.dispatchEvent(new Event('input',{bubbles:true}))});await page.locator('#focus').click();await page.waitForTimeout(300);await page.screenshot({path:`${out}/${scene}-close.png`});
  if(scene==='coast'){await page.locator('#canopy').check();assert.equal((await page.evaluate(()=>travelSceneState())).canopyOpen,true);await page.screenshot({path:`${out}/coast-cutaway.png`});await page.locator('#canopy').uncheck();}
  for(let i=0;i<3;i++){await page.locator(`[data-memory="${i}"]`).click();await page.waitForFunction(()=>{const i=document.querySelector('#memory-image');return i.complete&&i.naturalWidth>0});}
  await page.setViewportSize({width:390,height:844});await page.locator('#reset').click();await page.waitForTimeout(300);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:`${out}/${scene}-mobile.png`,fullPage:true});
  assert.deepEqual(errors,[]);results.push({scene,passed:true,state:await page.evaluate(()=>travelSceneState()),errors});await page.close();
 }}finally{await browser.close()}
 fs.writeFileSync(out+'/validation.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
