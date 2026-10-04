import test from 'node:test';
import assert from 'node:assert/strict';
import {installDisclosureMotion} from '../interactions.mjs';

function fixture(t,reduced=false) {
  const originals={matchMedia:globalThis.matchMedia,getComputedStyle:globalThis.getComputedStyle};
  t.after(()=>Object.assign(globalThis,originals));
  const preference={matches:reduced,addEventListener(_,handler){this.change=handler;}};
  globalThis.matchMedia=()=>preference;
  globalThis.getComputedStyle=()=>({getPropertyValue:key=>key==='--duration-reveal'?'240ms':'ease-out'});
  let handler;const root={addEventListener(_,fn){handler=fn;}};
  const classes=new Set(),animations=[];
  const details={tagName:'DETAILS',open:false,dataset:{},closest:()=>details,
    classList:{add:name=>classes.add(name),remove:name=>classes.delete(name)},
    getBoundingClientRect:()=>({height:details.visibleHeight ?? (details.open?180:40)}),
    animate(frames,options){const a={frames,options,cancel(){this.cancelled=true;delete details.visibleHeight;}};animations.push(a);return a;}};
  const summary={parentElement:details,closest:()=>summary,setAttribute(name,value){this[name]=value;}};
  installDisclosureMotion(root);
  return {details,classes,animations,preference,summary,click(){handler({target:summary,preventDefault(){}});}};
}

test('rapid reversal ends in the last requested state and a stale finish cannot hide content',t=>{
  const f=fixture(t);f.click();assert.equal(f.details.open,true);
  f.details.visibleHeight=100;f.click();delete f.details.visibleHeight;
  assert.equal(f.animations[0].cancelled,true);
  f.animations[0].onfinish();assert.equal(f.details.open,true,'closing content remains visible until its own finish');
  f.animations[1].onfinish();assert.equal(f.details.open,false);assert.equal(f.classes.size,0);
  f.click();f.animations[2].onfinish();assert.equal(f.details.open,true);assert.equal(f.summary['aria-expanded'],'true');
});

test('reduced motion changes disclosure state immediately without animation or clipping',t=>{
  const f=fixture(t,true);f.click();assert.equal(f.details.open,true);
  f.click();assert.equal(f.details.open,false);assert.equal(f.summary['aria-expanded'],'false');
  assert.equal(f.animations.length,0);assert.equal(f.classes.size,0);
});

test('enabling reduced motion during a close completes the requested state and clears the animation',t=>{
  const f=fixture(t);f.details.open=true;f.click();assert.equal(f.details.open,true);
  f.preference.matches=true;f.preference.change();
  assert.equal(f.details.open,false);assert.equal(f.animations[0].cancelled,true);assert.equal(f.classes.size,0);
  f.animations[0].onfinish();assert.equal(f.details.open,false);
});
