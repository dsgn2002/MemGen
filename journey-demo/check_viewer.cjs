// Run with the desktop's bundled Playwright and an isolated Chrome profile.
const {chromium} = require(process.env.JOURNEY_PLAYWRIGHT);
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(process.argv[2],{waitUntil:'networkidle'});
    await page.waitForFunction(()=>document.querySelector('model-viewer')?.loaded,{timeout:60000});
    const count=await page.locator('.stop-card').count();
    assert(count>=2&&count<=3);
    const originalWidth=await page.evaluate(()=>document.querySelector('model-viewer').getDimensions().x);
    await page.locator('#size').fill('1.5');
    await page.locator('#size').dispatchEvent('input');
    await page.waitForFunction(width=>document.querySelector('model-viewer').getDimensions().x>width*1.49,originalWidth);
    const exported=await page.evaluate(async()=>{const blob=await document.querySelector('model-viewer').exportScene({binary:true});const buffer=await blob.arrayBuffer();const view=new DataView(buffer);const json=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,20,view.getUint32(12,true))));const roots=json.scenes[json.scene||0].nodes.map(index=>json.nodes[index]);return {bytes:blob.size,scales:roots.map(node=>node.scale||(node.matrix?[node.matrix[0],node.matrix[5],node.matrix[10]]:[1,1,1]))}});
    assert(exported.bytes>1000);
    assert(exported.scales.some(scale=>scale.every(value=>Math.abs(value-1.5)<.001)));
    await page.locator('#reset-size').click();
    await page.waitForFunction(width=>Math.abs(document.querySelector('model-viewer').getDimensions().x-width)<.001,originalWidth);
    const initialOrbit=await page.evaluate(()=>document.querySelector('model-viewer').getCameraOrbit().theta);
    const area=await page.locator('model-viewer').boundingBox();
    await page.mouse.move(area.x+area.width*.5,area.y+area.height*.4);
    await page.mouse.down();await page.mouse.move(area.x+area.width*.7,area.y+area.height*.45,{steps:12});await page.mouse.up();
    await page.waitForFunction(theta=>Math.abs(document.querySelector('model-viewer').getCameraOrbit().theta-theta)>.05,initialOrbit);
    await page.locator('.stop-card').nth(1).click();
    assert.equal(await page.locator('.stop-card').nth(1).getAttribute('aria-pressed'),'true');
    assert.equal(await page.locator('.hotspot').nth(1).getAttribute('aria-pressed'),'true');
    await page.locator('#tour').click();
    assert.equal(await page.locator('#tour').getAttribute('aria-pressed'),'true');
    await page.locator('#overview').click();
    assert.equal(await page.locator('#tour').getAttribute('aria-pressed'),'false');
    await page.locator('#pipeline summary').click();
    await page.locator('[data-inspect="build"]').click();
    assert((await page.locator('#inspection').textContent()).includes('glb_reload'));
    await page.locator('#pipeline summary').click();
    await page.waitForTimeout(1500);
    await page.screenshot({path:process.argv[3],fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1));
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({model_loaded:true,stop_count:count,rotation_drag:'passed',geometry_scaling:'passed',scaled_glb_export:'passed',stop_selection:'passed',tour_controls:'passed',pipeline_inspector:'passed',mobile_overflow:'passed',page_errors:errors}));
  } finally {await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
