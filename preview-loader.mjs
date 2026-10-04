// One bounded queue per page. Reuse loaded image nodes across detail redraws.
export function createPreviewLoader({createImage=()=>new Image(),concurrency=3,timeoutMs=20000}={}) {
  const cache=new Map(),jobs=new Map(),queue=[];let active=0;
  const abortError=()=>Object.assign(new Error('Preview cancelled'),{name:'AbortError'});
  function pump() {
    while(active<concurrency && queue.length) {
      const job=queue.shift();if(job.done || !job.waiters.size)continue;
      active++;job.started=true;const img=createImage();job.img=img;
      img.decoding='async';img.referrerPolicy='no-referrer';
      const finish=(error)=>{
        if(job.done)return;job.done=true;clearTimeout(job.timer);img.onload=null;img.onerror=null;active--;jobs.delete(job.cacheKey);
        if(error) {img.removeAttribute('src');if(error.name!=='AbortError')cache.set(job.cacheKey,{error});}
        else cache.set(job.cacheKey,{img});
        for(const waiter of job.waiters){waiter.cleanup();error?waiter.reject(error):waiter.resolve(img);}
        job.waiters.clear();pump();
      };
      job.cancel=()=>finish(abortError());
      img.onload=()=>finish();
      img.onerror=()=>finish(Object.assign(new Error('Preview failed'),{kind:'failed'}));
      job.timer=setTimeout(()=>finish(Object.assign(new Error('Preview timed out'),{kind:'timeout'})),timeoutMs);
      img.src=job.url;
    }
  }
  function load(url,{signal,force=false,identity=''}={}) {
    if(signal?.aborted)return Promise.reject(abortError());
    const cacheKey=JSON.stringify([url,identity]),saved=cache.get(cacheKey);
    if(saved?.img)return Promise.resolve(saved.img);
    if(saved?.error && !force)return Promise.reject(saved.error);
    if(force)cache.delete(cacheKey);
    let job=jobs.get(cacheKey);
    if(!job){job={url,cacheKey,waiters:new Set(),done:false,started:false};jobs.set(cacheKey,job);queue.push(job);}
    return new Promise((resolve,reject)=>{
      const abort=()=>{
        job.waiters.delete(waiter);waiter.cleanup();reject(abortError());
        if(!job.waiters.size){if(job.started)job.cancel();else{job.done=true;jobs.delete(cacheKey);}}
      };
      const waiter={resolve,reject,cleanup:()=>signal?.removeEventListener('abort',abort)};
      job.waiters.add(waiter);signal?.addEventListener('abort',abort,{once:true});pump();
    });
  }
  return {load};
}
