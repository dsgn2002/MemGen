const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
async function main() {
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:950},deviceScaleFactor:1});
    const errors=[];page.on('pageerror', error=>errors.push(error.message));
    await page.goto(process.argv[2] || 'http://127.0.0.1:8768/', {waitUntil:'domcontentloaded',timeout:120000});
    await page.waitForFunction(()=>window.natureMapState && !window.natureMapState().loading, null, {timeout:180000});
    let state=await page.evaluate(()=>window.natureMapState());
    assert(state.triangles>1000);assert.deepEqual(state.assets,{coast:true,boat:true,traveler:true});
    await page.locator('#motion').click();
    state=await page.evaluate(()=>window.natureMapState());assert.equal(state.playing,false);
    await page.waitForTimeout(200);assert.equal((await page.evaluate(()=>window.natureMapState())).time,state.time);
    for(let i=0;i<3;i++) {
      await page.locator(`[data-stop="${i}"]`).click();
      assert.equal((await page.evaluate(()=>window.natureMapState())).active,i);
      await page.waitForFunction(()=>{const el=document.querySelector('#memory-image');return el.complete && el.naturalWidth>0});
    }
    await page.locator('#scale').evaluate(el=>{el.value='1.2';el.dispatchEvent(new Event('input',{bubbles:true}))});
    assert.equal((await page.evaluate(()=>window.natureMapState())).scale,1.2);
    await page.locator('#reset').click();assert.equal((await page.evaluate(()=>window.natureMapState())).scale,1);
    const box=await page.locator('#canvas').boundingBox();
    const before=(await page.evaluate(()=>window.natureMapState())).camera;
    await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();
    await page.mouse.move(box.x+box.width*.5+100,box.y+box.height*.5+30,{steps:12});await page.mouse.up();
    await page.waitForTimeout(150);
    assert.notDeepEqual((await page.evaluate(()=>window.natureMapState())).camera,before);
    await page.mouse.wheel(0,160);await page.waitForTimeout(200);
    await page.locator('#light').click();assert.equal((await page.evaluate(()=>window.natureMapState())).golden,true);
    await page.locator('#light').click();await page.locator('#reset').click();
    await page.locator('#motion').click();
    if(process.argv[3])await page.screenshot({path:process.argv[3]+'/sai-kung-map.jpg',fullPage:true,quality:85});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(process.argv[3])await page.screenshot({path:process.argv[3]+'/sai-kung-map-mobile.jpg',fullPage:true,quality:80});
    assert.deepEqual(errors,[]);
    const manifest=await (await page.request.get(new URL('manifest.json',page.url()).href)).json();
    assert.equal(manifest.omniverse_complete,true);
    console.log(JSON.stringify({passed:true,state:await page.evaluate(()=>window.natureMapState()),browserErrors:errors,mobileOverflow:false},null,2));
  } finally {await browser.close()}
}
main().catch(error=>{console.error(error);process.exitCode=1});
