import test from 'node:test';
import assert from 'node:assert/strict';
import {createPreviewLoader} from '../preview-loader.mjs';
function fixture(options={}) {
  const images=[];const loader=createPreviewLoader({...options,createImage:()=>{
    const img={removeAttribute(){this.removed=true;}};images.push(img);return img;
  }});return {loader,images};
}
test('limits concurrent requests and starts queued work when a slot frees',async()=>{
  const {loader,images}=fixture({concurrency:2});const promises=['a','b','c'].map(url=>loader.load(url));
  assert.deepEqual(images.map(i=>i.src),['a','b']);images[0].onload();assert.equal(images[2].src,'c');
  images[1].onload();images[2].onload();await Promise.all(promises);
});
test('shares one request and reuses the loaded image for subsequent redraws',async()=>{
  const {loader,images}=fixture();const a=loader.load('a'),b=loader.load('a');assert.equal(images.length,1);
  images[0].onload();assert.equal(await a,await b);assert.equal(await loader.load('a'),images[0]);assert.equal(images.length,1);
});
test('different recorded versions at the same URL do not share the preview memory',async()=>{
  const {loader,images}=fixture();const a=loader.load('a',{identity:'old'});images[0].onload();await a;
  const b=loader.load('a',{identity:'new'});assert.equal(images.length,2);images[1].onload();await b;
});
test('remembers failures until explicit retry instead of requesting on every redraw',async()=>{
  const {loader,images}=fixture();const failed=assert.rejects(loader.load('a'),/failed/);images[0].onerror();await failed;
  await assert.rejects(loader.load('a'),/failed/);assert.equal(images.length,1);
  const retry=loader.load('a',{force:true});assert.equal(images.length,2);images[1].onload();await retry;
});
test('aborting one subscriber keeps the shared request for another subscriber',async()=>{
  const {loader,images}=fixture(),a=new AbortController(),b=new AbortController();
  const canceled=assert.rejects(loader.load('a',{signal:a.signal}),{name:'AbortError'}),kept=loader.load('a',{signal:b.signal});
  a.abort();await canceled;assert.notEqual(images[0].removed,true);images[0].onload();await kept;
});
test('leaving the view cancels in-flight work and frees a queue slot',async()=>{
  const {loader,images}=fixture({concurrency:1}),controller=new AbortController();
  const canceled=assert.rejects(loader.load('a',{signal:controller.signal}),{name:'AbortError'}),next=loader.load('b');
  controller.abort();await canceled;assert.equal(images[0].removed,true);assert.equal(images[1].src,'b');images[1].onload();await next;
});
test('canceled queued work never starts a request',async()=>{
  const {loader,images}=fixture({concurrency:1}),controller=new AbortController(),first=loader.load('a');
  const canceled=assert.rejects(loader.load('b',{signal:controller.signal}),{name:'AbortError'});controller.abort();await canceled;
  images[0].onload();await first;assert.equal(images.length,1);
});
test('timeouts start only when the request begins, and a timeout frees the queue',async()=>{
  const {loader,images}=fixture({concurrency:1,timeoutMs:30});const first=assert.rejects(loader.load('a'),{kind:'timeout'});
  const next=loader.load('b');await first;assert.equal(images[1].src,'b');images[1].onload();await next;
});
