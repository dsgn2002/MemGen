// CPU fixture browser test. Never used by the deployed worker.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
(async()=>{
 const root=path.resolve(__dirname,'../..'),out=path.join(root,'tmp/upload-browser-qa');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8891/');
 await page.locator('#code').fill(fs.readFileSync(path.join(root,'tmp/upload-local-invite.txt'),'utf8').trim());
 await page.locator('#login-form button').click();await page.locator('#workspace').waitFor({state:'visible'});
 await page.locator('#new-project').click();await page.locator('[name=title]').fill('Browser fixture · city memory');
 await page.locator('[name=request]').fill('Highlight the visible person.');await page.locator('#create-form button').click();
 await page.locator('#project').waitFor({state:'visible'});
 // Simulate an interrupted first chunk, then reselect a same-size wrong file.
 const photo=fs.readFileSync(path.join(root,'tmp/city-refresh/office-avenue.jpg'));
 const projectId=new URL(page.url()).hash.slice(1),base='http://127.0.0.1:8891/api';
 const s=await (await page.request.get(base+'/session')).json(),headers={'X-CSRF-Token':s.csrf};
 const u=await (await page.request.post(`${base}/projects/${projectId}/uploads`,{headers,data:{name:'resume-fixture.jpg',size:photo.length,kind:'photo'}})).json();
 const chunk=await page.request.put(`${base}/projects/${projectId}/uploads/${u.id}?offset=0`,{headers:{...headers,'Content-Type':'application/octet-stream'},data:photo.subarray(0,1024)});
 if(!chunk.ok())throw new Error('Could not prepare interrupted upload.');
 await page.reload();await page.locator('#project').waitFor({state:'visible'});
 await page.getByText(/choose this file again to resume/).waitFor();
 const wrong=Buffer.from(photo);wrong[500]^=1;
 await page.locator('#files').setInputFiles({name:'resume-fixture.jpg',mimeType:'image/jpeg',buffer:wrong});
 await page.getByText('This file differs from the interrupted upload. Remove that upload and choose the correct file.',{exact:true}).waitFor();
 const partial=await (await page.request.get(`${base}/projects/${projectId}`)).json();
 if(partial.uploads[0].offset!==1024)throw new Error('Wrong resumed file appended data.');
 await page.locator('#files').setInputFiles({name:'resume-fixture.jpg',mimeType:'image/jpeg',buffer:photo});
 await page.getByText('Your media is uploaded and ready.',{exact:true}).waitFor();
 await page.screenshot({path:path.join(out,'upload-desktop.png'),fullPage:true});
 await page.locator('#analyze').click();await page.locator('#job-panel').waitFor({state:'visible'});
 execFileSync(path.join(root,'tmp/upload-venv/bin/python'),['-c',
 `import sys; from pathlib import Path; sys.path[:0]=['upload-app','upload-app/tests']; from test_upload import FixtureModel; from trip_upload.config import Settings; from trip_upload.store import Store; from trip_upload.pipeline import execute; s=Settings(Path('tmp/upload-local').resolve(),model='/explicit/test/checkpoint',secure_cookie=False); db=Store(s.data); j=db.claim(); assert j; execute(s,j['id'],FixtureModel()); db.finish(j['id'],'review')`],{cwd:root});
 await page.locator('#review').waitFor({state:'visible',timeout:20000});
 await page.locator('#approve').click();await page.getByText('Your choices are saved. Generation has not started.',{exact:true}).waitFor();
 await page.screenshot({path:path.join(out,'review-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'review-mobile.png'),fullPage:true});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 if(overflow||errors.length)throw new Error(JSON.stringify({overflow,errors}));
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({status:'passed',model:'explicit_test_double',resume_integrity:'passed',overflow,errors},null,2));
 await browser.close();console.log('Browser upload, queue, proposal, approval and mobile-layout checks passed (CPU fixture).');
})().catch(e=>{console.error(e);process.exit(1)});
