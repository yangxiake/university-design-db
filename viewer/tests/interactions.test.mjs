import test from 'node:test';
import assert from 'node:assert/strict';
import {installDisclosureMotion,installSectionTabs,installDialogFocus,syncSectionNavigation} from '../interactions.mjs';

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
  const controller=installDisclosureMotion(root);
  return {controller,details,classes,animations,preference,summary,click(){handler({target:summary,preventDefault(){}});}};
}

test('rapid reversal ends in the last requested state and a stale finish cannot hide content',t=>{
  const f=fixture(t);f.click();assert.equal(f.details.open,true);
  f.details.visibleHeight=100;f.click();delete f.details.visibleHeight;
  assert.equal(f.animations[0].cancelled,true);
  f.animations[0].onfinish();assert.equal(f.details.open,true,'closing content remains visible until its own finish');
  f.animations[1].onfinish();assert.equal(f.details.open,false);assert.equal(f.classes.size,0);
  f.click();f.animations[2].onfinish();assert.equal(f.details.open,true);assert.equal(f.summary['aria-expanded'],'true');
});

test('external filter trigger can reverse and immediately reset a pending disclosure',t=>{
  const f=fixture(t),trigger={setAttribute(name,value){this[name]=value;}};
  f.controller.toggle(f.details,trigger);assert.equal(trigger['aria-expanded'],'true');
  f.details.visibleHeight=100;f.controller.toggle(f.details,trigger);delete f.details.visibleHeight;
  assert.equal(trigger['aria-expanded'],'false');
  f.controller.setOpen(f.details,false,trigger,false);
  for(const animation of f.animations)animation.onfinish();
  assert.equal(f.details.open,false);assert.equal(f.classes.size,0);assert.equal(f.details.dataset.expanded,'false');
});

function tabsFixture(t,hash='') {
  const originals={location:globalThis.location,history:globalThis.history};t.after(()=>Object.assign(globalThis,originals));
  const calls=[],handlers={},panels=new Map();let focused;
  globalThis.location={href:'https://example.org/university-design-db/?query=PKU&school=4111010001'+hash,hash};
  globalThis.history=Object.fromEntries(['pushState','replaceState'].map(method=>[method,(_,__,url)=>{calls.push({method,url:String(url)});globalThis.location={href:String(url),hash:url.hash};}]));
  const tabs=['logos','colors','templates','content'].map(id=>({getAttribute:()=> '#'+id,
    setAttribute(name,value){this[name]=value;},removeAttribute(name){delete this[name];},focus(){focused=id;},closest(){return this;}}));
  for(const tab of tabs){panels.set(tab.getAttribute(),{hidden:false});tab.parentElement={querySelectorAll:()=>tabs};}
  const root={querySelectorAll:()=>tabs,querySelector:hash=>panels.get(hash),addEventListener(name,fn){handlers[name]=fn;}};
  installSectionTabs(root);syncSectionNavigation(root);
  return {tabs,panels,calls,get focused(){return focused;},click(index){handlers.click({target:tabs[index],preventDefault(){}});},key(index,key){handlers.keydown({target:tabs[index],key,preventDefault(){}});},sync:()=>syncSectionNavigation(root)};
}

test('tabs restore a deep link, expose only its panel and preserve school/filter URL on click',t=>{
  const f=tabsFixture(t,'#colors');
  assert.equal(f.tabs[1]['aria-selected'],'true');assert.equal(f.tabs[1].tabIndex,0);
  assert.equal(f.panels.get('#logos').hidden,true);assert.equal(f.panels.get('#colors').hidden,false);
  f.click(2);assert.equal(f.calls[0].method,'pushState');
  const url=new URL(f.calls[0].url);assert.equal(url.searchParams.get('query'),'PKU');assert.equal(url.searchParams.get('school'),'4111010001');assert.equal(url.hash,'#templates');
  assert.equal(f.tabs.filter(tab=>tab.tabIndex===0).length,1);
});

test('tab arrows wrap, Home/End focus and activate without adding history entries',t=>{
  const f=tabsFixture(t,'#unknown');assert.equal(f.tabs[0]['aria-selected'],'true');
  f.key(0,'ArrowLeft');assert.equal(f.focused,'content');assert.equal(f.panels.get('#content').hidden,false);
  f.key(3,'ArrowRight');assert.equal(f.focused,'logos');
  f.key(0,'End');assert.equal(f.focused,'content');f.key(3,'Home');assert.equal(f.focused,'logos');
  assert.ok(f.calls.every(call=>call.method==='replaceState'));
  globalThis.location.hash='#colors';f.sync();assert.equal(f.tabs[1].tabIndex,0);assert.equal(f.tabs[0].tabIndex,-1);
});

test('dialog Tab wraps between visible enabled controls in both directions',()=>{
  let keydown,prevented=0;
  const dialog={ownerDocument:{},addEventListener(_,fn){keydown=fn;},querySelectorAll:()=>controls};
  const control=visible=>({getClientRects:()=>visible?[{}]:[],focus(){dialog.ownerDocument.activeElement=this;}});
  const first=control(true),last=control(true),hidden=control(false),controls=[first,hidden,last];
  installDialogFocus(dialog);dialog.ownerDocument.activeElement=last;
  keydown({key:'Tab',shiftKey:false,preventDefault(){prevented++;}});assert.equal(dialog.ownerDocument.activeElement,first);
  keydown({key:'Tab',shiftKey:true,preventDefault(){prevented++;}});assert.equal(dialog.ownerDocument.activeElement,last);assert.equal(prevented,2);
  keydown({key:'Escape',preventDefault(){throw new Error('native Escape should remain available');}});
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
