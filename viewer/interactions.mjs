// Keep native details/summary keyboard behavior while giving every disclosure the same motion.
export function installDisclosureMotion(root=document) {
  const active=new Map(),preference=matchMedia('(prefers-reduced-motion: reduce)');
  const complete=(details,record)=>{
    if(active.get(details)!==record)return;
    details.open=record.open;details.classList.remove('is-disclosing');active.delete(details);
  };
  const setOpen=(details,open,trigger=details.querySelector?.('summary'),animate=true)=>{
    const previous=active.get(details);
    const start=details.getBoundingClientRect().height;
    previous?.animation.cancel();active.delete(details);
    trigger?.setAttribute('aria-expanded',String(open));details.querySelector?.('summary')?.setAttribute('aria-expanded',String(open));details.dataset.expanded=String(open);
    details.open=open;
    if(!animate || preference.matches || typeof details.animate!=='function') {
      details.classList.remove('is-disclosing');return;
    }
    const end=details.getBoundingClientRect().height;
    if(Math.abs(start-end)<1){details.classList.remove('is-disclosing');return;}
    // Keep content visible until the closing animation finishes.
    details.open=true;details.classList.add('is-disclosing');
    const style=getComputedStyle(details),duration=parseFloat(style.getPropertyValue('--duration-reveal')) || 160;
    const easing=style.getPropertyValue('--ease').trim() || 'ease-out';
    const animation=details.animate([{height:`${start}px`},{height:`${end}px`}],{duration,easing});
    const record={open,animation};active.set(details,record);
    animation.onfinish=()=>complete(details,record);
  };
  const toggle=(details,trigger)=>setOpen(details,active.has(details)?!active.get(details).open:!details.open,trigger);
  root.addEventListener('click',event=>{
    const summary=event.target.closest?.('summary'),details=summary?.parentElement;
    if(details?.tagName!=='DETAILS' || !details.closest('#filters, #detail'))return;
    event.preventDefault();toggle(details,summary);
  });
  preference.addEventListener('change',()=>{
    if(!preference.matches)return;
    for(const [details,record] of active){record.animation.cancel();complete(details,record);}
  });
  return {setOpen,toggle};
}

export function syncSectionNavigation(root=document) {
  const links=[...root.querySelectorAll('.subnav a')];
  const hash=links.some(link=>link.getAttribute('href')===location.hash)?location.hash:'#logos';
  for(const link of links) {
    const selected=link.getAttribute('href')===hash;
    link.setAttribute('aria-selected',String(selected));link.tabIndex=selected?0:-1;
    const panel=root.querySelector(link.getAttribute('href'));if(panel)panel.hidden=!selected;
    if(selected)link.setAttribute('aria-current','location');
    else link.removeAttribute('aria-current');
  }
}

// All panels are already loaded, so arrow keys can activate their tabs immediately.
export function installSectionTabs(root=document) {
  const activate=(tab,replace=false)=>{
    const url=new URL(location.href);url.hash=tab.getAttribute('href');
    if(url.hash!==location.hash)history[replace?'replaceState':'pushState'](null,'',url);
    syncSectionNavigation(root);
  };
  root.addEventListener('click',event=>{
    const tab=event.target.closest?.('.subnav a[role="tab"]');if(!tab)return;
    event.preventDefault();activate(tab);
  });
  root.addEventListener('keydown',event=>{
    const tab=event.target.closest?.('.subnav a[role="tab"]');if(!tab)return;
    const tabs=[...tab.parentElement.querySelectorAll('a[role="tab"]')],index=tabs.indexOf(tab);
    let next;
    if(event.key==='ArrowRight')next=tabs[(index+1)%tabs.length];
    else if(event.key==='ArrowLeft')next=tabs[(index+tabs.length-1)%tabs.length];
    else if(event.key==='Home')next=tabs[0];
    else if(event.key==='End')next=tabs[tabs.length-1];
    else if(event.key===' ' || event.key==='Enter')next=tab;
    if(!next)return;
    event.preventDefault();next.focus();activate(next,event.key!==' ' && event.key!=='Enter');
  });
}

export function installDialogFocus(dialog) {
  dialog.addEventListener('keydown',event=>{
    if(event.key!=='Tab')return;
    const controls=[...dialog.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')].filter(node=>node.getClientRects().length);
    if(!controls.length)return;
    const first=controls[0],last=controls[controls.length-1],current=dialog.ownerDocument.activeElement;
    if(event.shiftKey && current===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey && current===last){event.preventDefault();first.focus();}
  });
}
