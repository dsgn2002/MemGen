// Exercise the selection handoff in a temporary run, never selecting for the user.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main(){
  const run = path.resolve(process.argv[2]);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(),'journey-review-test-'));
  // Serve the current template with existing fixtures, leaving the user's selection intact.
  const output=path.join(temp,'output');fs.mkdirSync(output);
  for(const file of fs.readdirSync(path.join(run,'output'))){
    if(file!=='index.html')fs.symlinkSync(path.join(run,'output',file),path.join(output,file));
  }
  fs.copyFileSync(path.join(__dirname,'review.html'),path.join(output,'index.html'));
  const port = 18766, base = `http://127.0.0.1:${port}`;
  const server = spawn('python3',[path.join(__dirname,'serve_review.py'),'--run',temp,'--port',String(port)],{stdio:['ignore','pipe','pipe']});
  let browser;
  const checks = [];
  try{
    await new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>reject(Error('Review test server did not start')),10000);
      server.stdout.on('data',data=>{if(data.toString().includes('My Travel Journey review:')){clearTimeout(timeout);resolve()}});
      server.on('exit',code=>{clearTimeout(timeout);reject(Error(`Server exited: ${code}`))});
    });
    browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
    const page = await browser.newPage({viewport:{width:1440,height:1120},deviceScaleFactor:1});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base,{waitUntil:'networkidle'});
    await page.locator('#app').waitFor({state:'visible'});
    assert.equal(await page.locator('.card').count(),4);
    assert.equal(await page.locator('input[name=scene]:checked').count(),0);
    assert.equal(await page.locator('#save').isDisabled(),true);
    assert.equal((await (await page.request.get(base+'/api/selection')).json()).selection,null);
    assert(await page.locator('img').evaluateAll(imgs=>imgs.every(i=>i.complete&&i.naturalWidth===1280)));
    assert(await page.locator('img').evaluateAll(imgs=>imgs.every(i=>Math.abs(i.getBoundingClientRect().width/i.getBoundingClientRect().height-16/9)<0.01)));
    checks.push('All four original frames load; no default selection or generation.');
    await page.screenshot({path:path.join(temp,'review-desktop.jpg'),fullPage:true,quality:70});
    for(const id of ['sai-kung-boat','coastal-trail','yi-o-harvest','wu-kau-tang-group']){
      await page.locator(`[data-watch="${id}"]`).click();
      await page.waitForFunction(()=>document.getElementById('clip').readyState>=1);
      const duration=await page.locator('#clip').evaluate(v=>v.duration);
      assert(duration>=4&&duration<=7);
      await page.locator('#clip').evaluate(async v=>{await v.play()});
      await page.waitForFunction(()=>document.getElementById('clip').currentTime>0);
      await page.keyboard.press('Escape');
      await page.waitForFunction(()=>!document.getElementById('preview').open&&!document.getElementById('clip').hasAttribute('src'));
      assert.equal(await page.locator('#clip').getAttribute('src'),null);
    }
    checks.push('All four short source clips play; closing a preview stops playback.');
    const choice=page.locator('input[value="yi-o-harvest"]');
    await choice.focus();await page.keyboard.press('Space');
    assert.equal(await choice.isChecked(),true);
    const boat=page.locator('input[value="sai-kung-boat"]');
    await boat.check();
    assert.equal((await (await page.request.get(base+'/api/selection')).json()).selection,null);
    const note='Keep the traveler and leafy root vegetables prominent.';
    await page.locator('#notes').fill(note);
    await page.locator('#save').click();
    await page.waitForFunction(()=>document.getElementById('save').textContent==='Scene saved ✓');
    const selection=JSON.parse(fs.readFileSync(path.join(temp,'selection.json')));
    assert.equal(selection.schema_version,2);
    assert.deepEqual(selection.scenes.map(s=>s.id),['sai-kung-boat','yi-o-harvest']);
    assert.equal(selection.user_notes,note);
    assert.equal(selection.generation_started,false);
    assert.equal(selection.generation_requirements.unseen_detail_policy,'awaiting_user_choice');
    assert.deepEqual(selection.generation_requirements.interactions,['rotate','zoom','scale']);
    assert.equal(selection.source.sha256.length,64);
    assert.equal(selection.scenes.find(s=>s.id==='yi-o-harvest').references[0].timestamp_s,140);
    await page.reload({waitUntil:'networkidle'});
    assert.equal(await choice.isChecked(),true);
    assert.equal(await boat.isChecked(),true);
    assert.equal(await page.locator('#notes').inputValue(),note);
    assert.equal(await page.locator('#save').isDisabled(),true);
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#download').click()]);
    const exported=JSON.parse(fs.readFileSync(await download.path()));
    assert.deepEqual(exported,selection);
    checks.push('Multiple scenes, keyboard selection, explicit save, reload, notes, and downloaded brief agree.');
    await page.locator('input[value="coastal-trail"]').check();
    assert.deepEqual((await (await page.request.get(base+'/api/selection')).json()).selection.scenes.map(s=>s.id),['sai-kung-boat','yi-o-harvest']);
    await page.route('**/api/selection',async route=>{
      if(route.request().method()==='POST')await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'Test: scene could not be saved.'})});
      else await route.continue();
    });
    await page.locator('#save').click();
    await page.waitForFunction(()=>document.getElementById('save-status').textContent==='Test: scene could not be saved.');
    assert.equal(await page.locator('#save').isEnabled(),true);
    await page.unroute('**/api/selection');
    const headers={'Origin':base};
    const payload={scene_ids:['unknown'],review_version:selection.review_version,user_notes:''};
    assert.equal((await page.request.post(base+'/api/selection',{headers,data:payload})).status(),400);
    assert.equal((await page.request.post(base+'/api/selection',{headers,data:{...payload,scene_ids:['coastal-trail'],review_version:'stale'}})).status(),409);
    assert.equal((await page.request.post(base+'/api/selection',{headers:{Origin:'https://example.com'},data:payload})).status(),403);
    assert.equal((await page.request.post(base+'/api/selection',{headers,data:{...payload,scene_ids:['coastal-trail'],user_notes:'x'.repeat(2001)}})).status(),400);
    for(const scene_ids of [[],['coastal-trail','coastal-trail']]){
      assert.equal((await page.request.post(base+'/api/selection',{headers,data:{...payload,scene_ids}})).status(),400);
    }
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(temp,'selection.json'))).scenes.map(s=>s.id),['sai-kung-boat','yi-o-harvest']);
    checks.push('Unsaved changes and failed saves preserve prior choices; stale, invalid, duplicate, empty and cross-origin requests are rejected.');
    await page.locator('#save').click();
    await page.waitForFunction(()=>document.getElementById('save').disabled);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(temp,'selection.json'))).scenes.map(s=>s.id),['sai-kung-boat','coastal-trail','yi-o-harvest']);
    checks.push('The three-scene generation handoff preserves canonical scene order.');
    await page.setViewportSize({width:390,height:844});
    await page.reload({waitUntil:'networkidle'});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await page.screenshot({path:path.join(temp,'review-mobile.jpg'),fullPage:true,quality:70});
    assert.deepEqual(errors,[]);
    checks.push('Mobile layout has no horizontal overflow; no browser script errors.');
    fs.writeFileSync(path.join(run,'output/review-checks.json'),JSON.stringify({passed:true,checks,test_selection_location:'temporary isolated test run; not the user review',tested_at:new Date().toISOString()},null,2)+'\n');
    console.log(JSON.stringify({passed:true,checks},null,2));
  }finally{
    if(browser)await browser.close();
    server.kill('SIGTERM');
    fs.rmSync(temp,{recursive:true,force:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1});
