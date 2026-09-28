const assert=require('node:assert/strict');
const {webcrypto,createHash}=require('node:crypto');
globalThis.crypto=webcrypto;
require('../web/upload.js');
const hash=b=>createHash('sha256').update(b).digest('hex');
async function run({slow=false,lost=false}={}) {
 const data=Buffer.alloc(2500000,77),file=new Blob([data]);file.name='sample.mp4';
 let elapsed=0,offset=0,failed=false;const parts=[],sizes=[],stored=[],messages=[];
 async function api(url,options={}) {
  if(options.method==='PUT') {
   const start=Number(new URL('http://test'+url).searchParams.get('offset'));
   assert.equal(start,offset,'Must resume from server offset without duplicating bytes');
   const bytes=Buffer.from(await options.body.arrayBuffer());sizes.push(bytes.length);
   stored.push(bytes);parts.push({offset,size:bytes.length,sha256:hash(bytes)});offset+=bytes.length;
   elapsed+=slow?12000:500;
   if(lost&&!failed){failed=true;throw new TypeError('Response lost after commit');}
   return {offset};
  }
  return {uploads:[{id:'u',offset,parts}]};
 }
 await TripUpload.transfer(file,{id:'u',offset:0},'p',api,s=>messages.push(s),{now:()=>elapsed,delay:async()=>{}});
 assert.equal(offset,data.length);assert.deepEqual(Buffer.concat(stored),data);
 assert.equal(sizes[0],128*1024);assert.ok(Math.max(...sizes)<=1024*1024);
 assert.ok(messages.at(-1).includes('100% saved on Spark'));
 if(slow)assert.ok(sizes.includes(32*1024));
 if(lost)assert.ok(messages.some(m=>m.includes('reconnecting')));
}
(async()=>{
 await run();await run({slow:true});await run({lost:true});
 const file=new Blob(['changed']);file.name='same-name.mp4';
 await assert.rejects(()=>TripUpload.verify(file,{parts:[{offset:0,size:7,sha256:hash(Buffer.from('correct'))}]}),/differs/);
 console.log('PASS: adaptive chunks, slow-link sizing, lost acknowledgement recovery, and resumed-file integrity.');
})().catch(e=>{console.error(e);process.exitCode=1;});
