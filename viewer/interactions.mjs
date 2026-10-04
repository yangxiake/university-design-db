// Keep native details/summary keyboard behavior while giving every disclosure the same motion.
export function installDisclosureMotion(root=document) {
  const active=new Map(),preference=matchMedia('(prefers-reduced-motion: reduce)');
  const complete=(details,record)=>{
    if(active.get(details)!==record)return;
    details.open=record.open;details.classList.remove('is-disclosing');active.delete(details);
  };
  root.addEventListener('click',event=>{
    const summary=event.target.closest?.('summary'),details=summary?.parentElement;
    if(details?.tagName!=='DETAILS' || !details.closest('#filters, #detail'))return;
    event.preventDefault();
    const previous=active.get(details),open=previous?!previous.open:!details.open;
    const start=details.getBoundingClientRect().height;
    previous?.animation.cancel();active.delete(details);
    summary.setAttribute('aria-expanded',String(open));details.dataset.expanded=String(open);
    details.open=open;
    if(preference.matches || typeof details.animate!=='function') {
      details.classList.remove('is-disclosing');return;
    }
    const end=details.getBoundingClientRect().height;
    if(Math.abs(start-end)<1){details.classList.remove('is-disclosing');return;}
    // Keep content visible until the closing animation finishes.
    details.open=true;details.classList.add('is-disclosing');
    const style=getComputedStyle(details),duration=parseFloat(style.getPropertyValue('--duration-reveal')) || 240;
    const easing=style.getPropertyValue('--ease').trim() || 'ease-out';
    const animation=details.animate([{height:`${start}px`},{height:`${end}px`}],{duration,easing});
    const record={open,animation};active.set(details,record);
    animation.onfinish=()=>complete(details,record);
  });
  preference.addEventListener('change',()=>{
    if(!preference.matches)return;
    for(const [details,record] of active){record.animation.cancel();complete(details,record);}
  });
}

export function syncSectionNavigation(root=document) {
  const links=[...root.querySelectorAll('.subnav a')];
  const hash=links.some(link=>link.getAttribute('href')===location.hash)?location.hash:'#logos';
  for(const link of links) {
    if(link.getAttribute('href')===hash)link.setAttribute('aria-current','location');
    else link.removeAttribute('aria-current');
  }
}
