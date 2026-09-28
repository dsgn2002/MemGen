// Inspect actual Spark results through an SSH loopback forward. No model fixture.
// Chrome supports the production Secure cookie on its trusted loopback origin.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs'),path=require('path');
(async()=>{
 const root=path.resolve(__dirname,'../..');
 const access=JSON.parse(fs.readFileSync(path.join(root,'tmp/upload-live-access.json'),'utf8'));
 const base='http://127.0.0.1:8892';
 const out=path.join(root,'tmp/upload-live-browser-qa');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try {
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  const page=await context.newPage(),errors=[],results=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/');
  await page.locator('#code').fill(access.code);
  await page.locator('#login-form button').click();
  await page.locator('#workspace').waitFor({state:'visible'});
  for(const project of access.projects){
   await page.goto('about:blank');
   await page.goto(base+'/#'+project.id);
   await page.locator('#project').waitFor({state:'visible'});
   await page.waitForFunction(()=>document.querySelector('#project-title').textContent.length>0);
   const state=await page.evaluate(async id=>(await fetch('/api/projects/'+id)).json(),project.id);
   if(['review','approved'].includes(state.status)){
    await page.locator('#review').waitFor({state:'visible'});
    await page.locator('.moment-card').first().waitFor();
    await page.waitForFunction(()=>[...document.querySelectorAll('.moment-card img')].every(i=>i.complete&&i.naturalWidth>0));
    for(const video of await page.locator('.moment-card video').all()){
     await video.evaluate(async v=>{
      v.preload='auto';v.load();
      await new Promise((resolve,reject)=>{
       const timer=setTimeout(()=>reject(new Error('Preview video load timed out')),30000);
       const ready=()=>{clearTimeout(timer);resolve();};
       if(v.readyState>=2)ready();else{v.addEventListener('loadeddata',ready,{once:true});v.addEventListener('error',()=>{clearTimeout(timer);reject(new Error('Preview video decode failed'));},{once:true});}
      });
      await v.play();await new Promise(resolve=>setTimeout(resolve,200));v.pause();
      if(v.currentTime<=0)throw new Error('Preview video did not advance.');
     });
    }
   }
   await page.screenshot({path:path.join(out,project.kind+'-desktop.png'),fullPage:true});
   await page.setViewportSize({width:390,height:844});
   await page.screenshot({path:path.join(out,project.kind+'-mobile.png'),fullPage:true});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   if(overflow)throw new Error('Mobile overflow: '+project.kind);
   results.push({kind:project.kind,status:state.status,stage:state.job.stage,overflow,
                 video_playback:project.kind==='video'&&['review','approved'].includes(state.status)?'passed':'not_applicable'});
   await page.setViewportSize({width:1280,height:900});
  }
  if(errors.length)throw new Error(JSON.stringify(errors));
  const result={transport:'SSH loopback; native Chrome login, no public HTTPS claim',model:'local_qwen',results,errors};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
