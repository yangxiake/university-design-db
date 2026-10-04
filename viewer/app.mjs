import {TAGS,KINDS,COLOR_STATUS,ACCESS,METHODS,safeUrl,matchesSchool,materialMatches,
  previewMode,previewBackground,resourceGroup,formatSize,groupLogoAssets,groupColors,groupResources,
  groupPresentations,previewSources} from './model.mjs?v=20261003-ui4.1';
import {createPreviewLoader} from './preview-loader.mjs?v=20261003-ui4.2';
import {installDisclosureMotion,syncSectionNavigation} from './interactions.mjs?v=20261003-ui5.1';

const $ = id => document.getElementById(id);
const PAGE_SIZE = 24;
const fields = ['query','province','type','source','format','kind','transparent','status','colorStatus'];
const advancedFields = ['source','format','kind','transparent','status','colorStatus'];
const state = {catalog:null,selected:null,page:0,rows:[],loadId:0,bundles:new Map(),background:'auto'};
state.localFiles={};
const previewLoader=createPreviewLoader();
const chosenVersions=new Map(),mountedImages=new Set();let previewScope=new AbortController();
function clearPreviews() {
  previewScope.abort();previewScope=new AbortController();
  for(const img of mountedImages)img.remove();mountedImages.clear();
}
const availability = {unresearched:'尚未调查',not_found:'已检索，尚未找到',conflict:'来源冲突，暂停选择'};
function el(tag, text='', className='') {
  const node = document.createElement(tag);
  if (text !== '') node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
function button(label, action, className='button') {
  const node = el('button',label,className); node.type='button'; node.addEventListener('click',action); return node;
}
function link(label, url, className='') {
  const node = el('a',label,className); const href = safeUrl(url);
  if (href) {node.href=href; node.target='_blank'; node.rel='noopener noreferrer';}
  else {node.removeAttribute('href'); node.title='来源网址未记录或不可识别';}
  return node;
}
function metadata(pairs) {
  const dl = el('dl','','metadata');
  for (const [key,value] of pairs) {dl.append(el('dt',key),el('dd',value == null || value === '' ? '未记录' : value));}
  return dl;
}
function chip(text,kind='') {return el('span',text,'chip '+kind);}
function provenance(entry) {
  const details = el('details','','source-details'); details.append(el('summary','来源、版本与使用说明'));
  const source = el('p'); source.append('资料来源：',link(entry.source || '未记录',entry.source)); details.append(source);
  details.append(metadata([['采集日期',entry.checked_at],['核验状态',{auto:'自动采集',human:'人工核验',unverified:'未核验'}[entry.verified]],
    ...(entry.source_as_of ? [['原资料时间',entry.source_as_of]] : []),
    ...(entry.repository || entry.upstream_repository ? [['社区仓库',entry.repository || entry.upstream_repository]] : []),
    ...(entry.commit || entry.upstream_commit ? [['固定提交',entry.commit || entry.upstream_commit]] : [])]));
  for (const [key,label] of [['basis','依据'],['note','来源说明'],['usage_note','使用说明'],
    ['rights_holder','图形权利人'],['asset_license','独立图形许可'],['repository_license','仓库代码/数据许可'],['license','资源许可'],
    ['upstream_license','上游数据许可'],['sha256','文件哈希'],['container_sha256','容器哈希'],['archive_sha256','压缩包哈希']]) {
    if (entry[key]) details.append(el('p',`${label}：${entry[key]}`));
  }
  if ('asset_license' in entry && !entry.asset_license) details.append(el('p','独立图形许可未取得明确声明；仓库代码许可不能替代学校标识授权。'));
  if(entry.search_sources?.length) {const list=el('ul');for(const url of entry.search_sources){const item=el('li');item.append(link(url,url));list.append(item);}details.append(el('p','已检索入口：'),list);}
  return details;
}
function sourceCollection(entries,title,extra=()=>[]) {
  const details=el('details','','source-details source-collection');details.append(el('summary',title));
  entries.forEach((entry,index)=>{
    const item=el('div','','source-entry');item.append(el('h5',`${index+1}. ${entry.variant || entry.title || entry.label || '资料来源'}`),...extra(entry));
    const evidence=provenance(entry);evidence.open=true;item.append(evidence);details.append(item);
  });return details;
}
function toast(message) {
  $('toast').textContent=message; $('toast').hidden=false;
  clearTimeout(toast.timer); toast.timer=setTimeout(()=>{$('toast').hidden=true;},3500);
}
async function copy(value) {
  try {await navigator.clipboard.writeText(value); toast('已复制，引用时请保留来源。');}
  catch {toast('浏览器未允许复制；可下载单校资料，或选中文本手动复制。');}
}
function section(id,title,desc) {
  const node = el('section','','section'); node.id=id;
  const heading = el('div','','section-title'); heading.append(el('h3',title)); node.append(heading);
  if (desc) node.append(el('p',desc,'section-desc'));
  return node;
}
function filters() {return Object.fromEntries(fields.map(key=>[key,$(key).value]));}
function writeUrl(push=false) {
  const u=new URL(location.href); u.search='';
  for (const [key,value] of Object.entries(filters())) if (value && !(key==='type' && value==='all')) u.searchParams.set(key,value);
  if (state.selected) u.searchParams.set('school',state.selected.school_code);
  history[push?'pushState':'replaceState'](null,'',u);
}
function restoreFilters() {
  const params=new URL(location.href).searchParams;
  for (const key of fields) {const value=params.get(key) || (key==='type'?'all':'');
    $(key).value=key==='query' || [...$(key).options].some(o=>o.value===value)?value:'';}
  if (!$('type').value) $('type').value='all';
  updateFilterControls();
  document.querySelector('.advanced').open=advancedFields.some(key=>$(key).value);
}
function updateFilterControls() {
  const type=$('type').value;
  for (const key of ['kind','transparent']) {$(key).disabled=!['all','logo'].includes(type); if ($(key).disabled) $(key).value='';}
  for (const key of ['format','status']) {$(key).disabled=type==='color'; if ($(key).disabled) $(key).value='';}
  const count=advancedFields.filter(key=>$(key).value).length;
  $('filter-summary').textContent=count?`已启用 ${count} 项条件`:'来源、格式与标识样式';
}
function refreshResults(updateUrl=true) {
  if (!state.catalog) return;
  // A filter change invalidates any school request that has not finished yet.
  state.loadId++;
  updateFilterControls();
  const f=filters(); state.rows=state.catalog.schools.filter(s=>matchesSchool(s,f)); state.page=0;
  if (state.selected && !state.rows.some(s=>s.school_code===state.selected.school_code)) {state.selected=null; state.loadId++; welcome();}
  else if (state.selected) renderSchool(state.selected);
  else welcome();
  renderList(); if (updateUrl) writeUrl();
}
function renderList() {
  const pages=Math.max(1,Math.ceil(state.rows.length/PAGE_SIZE)); state.page=Math.min(state.page,pages-1);
  $('result-count').textContent=`找到 ${state.rows.length.toLocaleString()} 所学校`;
  const list=$('school-list'); list.replaceChildren();
  if (!state.rows.length) list.append(el('p','暂无匹配学校。可减少素材条件或重置筛选。','empty'));
  for (const school of state.rows.slice(state.page*PAGE_SIZE,(state.page+1)*PAGE_SIZE)) {
    const card=button('',()=>selectSchool(school.school_code),'school-card'+(state.selected?.school_code===school.school_code?' selected':''));
    card.setAttribute('aria-label',`查看${school.name_zh}资料`); card.append(el('h3',school.name_zh),el('div',`${school.province} · ${school.school_code}`,'school-meta'));
    card.setAttribute('aria-pressed',String(state.selected?.school_code===school.school_code));
    const counts=el('div','','school-counts');
    counts.append(el('span',`标识记录 ${school.logo_count}`),el('span',`色卡记录 ${school.color_count}`),el('span',`模板入口 ${school.template_count}`));
    card.append(counts,el('div',COLOR_STATUS[school.color_status],'school-status')); list.append(card);
  }
  $('page-info').textContent=state.rows.length?`${state.page+1} / ${pages}`:'0 / 0';
  $('prev').disabled=state.page===0; $('next').disabled=!state.rows.length || state.page>=pages-1;
}
function welcome() {
  clearPreviews();
  const node=el('div','','welcome'); node.append(el('span','从学校开始','section-kicker'),el('h2','选择学校，开始查找素材。'),
    el('p','选择学校后，比较校徽和校名标识，复制配色，或查看 PPT 模板。每项资料均保留来源说明。'));
  if (state.catalog) {const actions=el('div','','welcome-actions');
    for (const [code,label] of [['4111010003','清华大学'],['4111010001','北京大学'],['4131010276','华东政法大学']])
      actions.append(button(label,()=>{for(const key of fields)$(key).value=key==='type'?'all':'';refreshResults(false);selectSchool(code);}));
    node.append(actions);}
  $('detail').replaceChildren(node);
}
async function getBundle(province) {
  if (!state.bundles.has(province)) {
    const request=fetch(`data/provinces/${encodeURIComponent(province)}.json`).then(r=>{
      if(!r.ok)throw new Error(`HTTP ${r.status}`); return r.json();
    }).catch(error=>{state.bundles.delete(province);throw error;});
    state.bundles.set(province,request);
  }
  return state.bundles.get(province);
}
async function selectSchool(code,push=true) {
  clearTimeout(debounce);
  clearPreviews();
  const row=state.catalog.schools.find(s=>s.school_code===code);
  if (!row) {state.selected=null; $('detail').replaceChildren(el('p','此标识码不在当前本科范围内。请从目录重新选择学校。','empty'));return;}
  const loadId=++state.loadId;
  state.selected=null;
  $('detail').replaceChildren(el('p',`正在载入${row.name_zh}的资料…`,'empty'));
  try {
    const bundle=await getBundle(row.province);
    if(loadId!==state.loadId)return;
    const school=bundle.schools[code]; if(!school)throw new Error('School missing in regional bundle');
    state.selected=school;renderSchool(school);renderList();if(push)writeUrl(true);
    if(matchMedia('(max-width:760px)').matches)$('detail').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
  } catch {if(loadId!==state.loadId)return;
    $('detail').replaceChildren(el('p','单校资料载入失败。已取得的检索目录仍可使用。','empty'),button('重新载入',()=>selectSchool(code,push)));}
}
function visible(descriptor) {return materialMatches(descriptor,filters());}
function renderSchool(school) {
  clearPreviews();
  const header=el('header','','detail-header'); header.append(el('div',`${school.province} / ${school.city} / ${school.school_code}`,'breadcrumb'),el('h2',school.name_zh));
  const tags=el('div','','tags'); for(const tag of school.scope_tags) if(['double_first','private','cooperative','vocational_undergraduate'].includes(tag))tags.append(el('span',TAGS[tag] || tag,'tag'));header.append(tags);
  const actions=el('div','','actions');const site=school.identity.official_website;
  actions.append(button('复制该校资料',()=>copy(JSON.stringify(school,null,2)),'button primary'),button('下载单校 JSON',()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(school,null,2)+'\n'],{type:'application/json'}));
    const a=el('a');a.href=url;a.download=`${school.school_code}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }));
  if(site.availability==='found')actions.append(link('学校官网 ↗',site.value,'button'));
  else actions.append(chip(`官网：${availability[site.availability] || site.availability}`));
  if(/^universities\/[^/]+\/\d{10}\/profile\.yaml$/.test(school.profile_path)) {const a=el('a','完整档案','button');a.href='../'+school.profile_path;actions.append(a);}
  header.append(actions);
  const jsonDetails=el('details','','source-details');jsonDetails.append(el('summary','查看 / 手动复制单校 JSON'));
  const jsonText=el('textarea','','json-data');jsonText.readOnly=true;jsonText.rows=8;
  jsonText.setAttribute('aria-label','单校 JSON 资料');jsonText.value=JSON.stringify(school,null,2);
  jsonDetails.append(jsonText);header.append(jsonDetails);
  const nav=el('nav','','subnav');nav.setAttribute('aria-label','单校资料分区');
  for(const [id,label] of [['logos','标识'],['colors','配色'],['templates','模板'],['content','介绍']]) {const a=el('a',label);a.href='#'+id;nav.append(a);}
  $('detail').replaceChildren(header,nav,renderLogos(school),renderColors(school),renderTemplates(school),renderContent(school));
  syncSectionNavigation();
}
function renderLogos(school) {
  const assets=school.logos.candidates.filter(a=>visible({type:'logo',official:a.official,formats:a.format?[a.format.toUpperCase()]:[],kind:a.kind,transparent:a.transparent_background,status:a.access_status}));
  const families=groupLogoAssets(assets);
  const sec=section('logos',`标识 · ${families.length} 组`,'同类标识集中展示，可切换文件版本；完全相同文件的多个来源合并保留。');
  const choice=el('label','预览背景 ','background-choice');const select=el('select'); select.setAttribute('aria-label','标识预览背景');
  for(const [value,label] of [['auto','自动'],['light','浅色'],['dark','深色'],['checker','透明棋盘']]) {const opt=el('option',label);opt.value=value;select.append(opt);}select.value=state.background;
  select.addEventListener('change',()=>{state.background=select.value; sec.querySelectorAll('.asset-preview').forEach(box=>{box.dataset.background=previewBackground(JSON.parse(box.dataset.assetHint),state.background);});});
  choice.append(select);sec.querySelector('.section-title').append(choice);
  if(assets.length)sec.append(el('p',`${families.reduce((n,f)=>n+f.versions.length,0)} 个文件版本 · ${assets.length} 条来源记录`,'section-desc'));
  const grid=el('div','','logo-grid');
  for(const family of families)grid.append(logoCard(family,school));sec.append(grid);
  if(school.logos.candidates.length){const note=el('details','','source-details');note.append(el('summary','预览与资料选择说明'),el('p',school.logos.reason),el('p','预览背景不代表学校标准色。网页载入结果与历史文件读取记录分别保留；不同版本的图形或许可可能不同。'));sec.append(note);}
  if(!assets.length) sec.append(el('p',school.logos.candidates.length?'当前素材条件下没有标识记录；可清除条件查看全部候选。':'逐文件标识集合为空。官网或VI调查状态见下方，不能推断学校没有标识。','empty'));
  if(!school.logos.candidates.length)for(const [key,label] of [['vi_url','VI入口'],['badge_description','标识简述']]) {const fact=school.logos.lookup_status[key];sec.append(el('p',`${label}：${availability[fact.availability] || '已记录'}`,'section-desc'),provenance(fact));}
  return sec;
}
function logoCard(family,school) {
  const card=el('div','','asset-card');card.dataset.family=family.key;
  const key=`${school.school_code}:${family.key}`;
  const rank=a=>state.localFiles[a.sha256]?0:previewMode(a)==='auto'?(a.official?1:2):previewMode(a)==='manual'?3:4;
  const primary=v=>[...v.entries].sort((a,b)=>rank(a)-rank(b) || Number(b.asset_id===school.logos.recommended_asset_id)-Number(a.asset_id===school.logos.recommended_asset_id))[0];
  const versions=[...family.versions].sort((a,b)=>rank(primary(a))-rank(primary(b)));
  let version=versions.find(v=>v.key===chosenVersions.get(key)) || versions[0];let controller,detach,image;
  const ownerSignal=previewScope.signal;
  function showVersion() {
    controller?.abort();detach?.();if(image){image.remove();mountedImages.delete(image);image=null;}
    controller=new AbortController();const abort=()=>controller.abort();ownerSignal.addEventListener('abort',abort,{once:true});detach=()=>ownerSignal.removeEventListener('abort',abort);
    const asset=primary(version),mode=previewMode(asset);card.dataset.assetId=asset.asset_id;
    const box=el('div','','asset-preview');box.dataset.background=previewBackground(asset,state.background);box.dataset.assetHint=JSON.stringify({preview_background_hint:asset.preview_background_hint,kind:asset.kind,transparent_background:asset.transparent_background});
    const placeholder=el('div','','preview-placeholder');box.append(placeholder);
    const body=el('div','','asset-body');body.append(el('h4',({badge:'校徽',wordmark:'校名文字',combination:'校徽与校名',site_identity:'官网标识',anniversary:'纪念标识'}[family.kind] || '标识文件')));
    if(versions.length>1){const label=el('label','文件版本','version-choice'),choice=el('select');choice.setAttribute('aria-label',`${school.name_zh}${KINDS[family.kind] || '标识'}文件版本`);
      versions.forEach((v,i)=>{const a=primary(v),size=a.width&&a.height?`${a.width}×${a.height}`:`版本 ${i+1}`;const option=el('option',`${a.format?.toUpperCase() || '未知格式'} · ${a.official?'校方':'社区'} · ${a.variant || size}${a.download_kind==='archive_member'?' · 包内文件':''}`);option.value=v.key;choice.append(option);});
      choice.value=version.key;choice.addEventListener('change',()=>{version=versions.find(v=>v.key===choice.value);chosenVersions.set(key,version.key);showVersion();});label.append(choice);body.append(label);
    }
    const chips=el('div','','chips');chips.append(chip(asset.official?'校方发布':'社区来源',asset.official?'official':'reference'),chip(asset.format?.toUpperCase() || '未知格式'));
    if(version.entries.length>1)chips.append(chip(`${version.entries.length} 条来源`));body.append(chips);
    body.append(el('p',[asset.width&&asset.height?`${asset.width} × ${asset.height}`:'尺寸未记录',asset.transparent_background===true?'透明背景':asset.transparent_background===false?'非透明背景':'背景未记录'].join(' · '),'file-facts'));
    const status=el('div','等待预览…','preview-status');body.append(status);
    const links=el('div','','small-links'),fileLink=link(mode==='archive'?'原压缩包 ↗':mode==='document'?'原 PDF ↗':'原文件 ↗',asset.archive_url || asset.url);
    links.append(fileLink,link('发布来源 ↗',asset.source));
    const sources=previewSources(version.entries,state.localFiles),signal=controller.signal;
    async function startImage(force=false) {
      if(signal.aborted)return;placeholder.replaceChildren();if(!placeholder.isConnected)box.append(placeholder);
      if(image){image.remove();mountedImages.delete(image);image=null;}
      for(let i=0;i<sources.length;i++) {
        const source=sources[i];placeholder.textContent=source.local?'正在载入本地已核验文件…':i?'正在尝试同一文件的其他来源…':'正在载入原来源图形…';status.textContent='预览加载中…';
        try {
          const loaded=await previewLoader.load(new URL(source.url,location.href).href,{signal,force,identity:version.key});
          if(signal.aborted)return;image=mountedImages.has(loaded)?loaded.cloneNode():loaded;image.alt=asset.title;placeholder.remove();box.append(image);mountedImages.add(image);status.textContent=source.local?'预览已载入 · 本地已核验文件':'预览已载入 · 原来源';
          if(!source.local)fileLink.href=source.url;return;
        } catch(error) {if(error.name==='AbortError')return;}
      }
      placeholder.textContent=versions.length>1?'暂时无法预览，可切换文件版本或打开原文件。':'暂时无法预览，原文件与来源仍可查阅。';status.textContent='本次预览未完成';placeholder.append(button('重新尝试',()=>startImage(true),'quiet'));
    }
    if(sources.some(s=>s.local) || version.entries.some(a=>previewMode(a)==='auto')) {placeholder.textContent='等待预览…';queueMicrotask(()=>{if(card.isConnected&&!signal.aborted)startImage();});}
    else if(sources.length){placeholder.textContent='文件尚未成功读取，可尝试预览。';placeholder.append(button('尝试载入图形',()=>startImage(),'quiet'));status.textContent='尚未预览';}
    else {placeholder.textContent=mode==='archive'?'标识位于压缩包中\n请从下方原包获取':mode==='document'?`标识位于 PDF 第 ${asset.document_page} 页\n请从下方原 PDF 获取`:'此文件暂不支持图形预览';status.textContent='未提供直接图像预览';}
    body.append(links);
    const yesNo=v=>v===true?'是':v===false?'否':'未记录';
    body.append(sourceCollection(version.entries,`文件与来源说明 · ${version.entries.length}`,a=>[metadata([['文件读取',ACCESS[a.access_status] || a.access_status],['格式',a.format?.toUpperCase()],['尺寸',a.width&&a.height?`${a.width} × ${a.height}`:'未记录'],['矢量表示',yesNo(a.vector)],['透明背景',yesNo(a.transparent_background)],['文件名',a.file_name],...(a.archive_member?[['包内路径',a.archive_member_display || a.archive_member]]:[]),...(a.download_kind==='document_page'?[['PDF页码',`${a.document_page} / ${a.document_page_count}`]]:[])]),link('原文件 / 原包 ↗',a.archive_url || a.url)]));
    card.replaceChildren(box,body);
  }
  showVersion();return card;
}
function renderColors(school) {
  const colors=school.colors;const sec=section('colors','配色证据','官方数字色、印刷色与设计参考分开显示。CMYK/Pantone没有数字屏幕值时，不自动换算HEX。');
  sec.append(el('p',`${COLOR_STATUS[colors.screen_status]} · ${colors.reason}`,colors.screen_status==='conflict'?'callout warning':'callout'));
  if(colors.screen_primary){const selected=el('div','','actions');selected.append(el('span',`当前屏幕选择 ${colors.screen_primary.value}`,'hex'),button('复制色值',()=>copy(colors.screen_primary.value),'quiet'));sec.append(selected,provenance(colors.screen_primary));}
  for(const conflict of colors.conflicts) {
    const block=el('div','','color-section');block.append(el('h4',conflict.field==='visual.color_primary'?'主色来源冲突':'辅色 / 并列色来源冲突'));
    const grid=el('div','','color-grid');for(const group of groupColors(conflict.fact.candidates.map(c=>({...c,checked_at:conflict.fact.checked_at,verified:conflict.fact.verified,method:'conflict',basis:c.basis || conflict.fact.note || '保留来源候选，未自动选择。'}))))grid.append(colorCard(group));block.append(grid);sec.append(block);
  }
  for(const [key,label] of [['official_digital','校方数字色'],['official_print_only','校方印刷色'],['references','设计与社区参考色']]) {
    const entries=colors[key].filter(c=>visible({type:'color',official:c.method==='official_vi',formats:[],status:c.value==null?'print_only':c.method}));
    if(!entries.length)continue;const groups=groupColors(entries),block=el('div','','color-section');block.append(el('h4',`${label} · ${groups.length} 种色值`));const grid=el('div','','color-grid');for(const group of groups)grid.append(colorCard(group));block.append(grid);sec.append(block);
  }
  if(!['official_digital','official_print_only','references'].some(k=>colors[k].length) && !colors.conflicts.length)sec.append(el('p','结构化配色集合为空。当前调查状态与原主色事实仍保留。','empty'),provenance(colors.primary_fact));
  return sec;
}
function colorCard(group) {
  const entries=group.entries,color=entries[0];
  const card=el('div','','color-card');const valid=/^#[0-9a-f]{6}$/i.test(color.value || '');
  const swatch=el('div',valid?'':'仅印刷证据','swatch'+(valid?'':' print-only'));if(valid)swatch.style.backgroundColor=color.value;
  const body=el('div','','color-body');body.append(el('h5',color.label || {primary:'主色记录',secondary:'辅色 / 并列记录',reference:'参考色',accent:'强调色'}[color.role] || '来源候选'));
  body.append(el('div',valid?color.value:'屏幕值为空','hex'),el('p',[...new Set(entries.map(c=>!valid && c.method==='official_vi'?'校方VI印刷证据':METHODS[c.method] || '来源存在冲突'))].join(' · ')));
  if(entries.length>1)body.append(chip(`${entries.length} 条来源合并`));
  if(color.rgb)body.append(el('p','RGB '+color.rgb.join(' / ')));
  if(color.cmyk)body.append(el('p','CMYK '+color.cmyk.join(' / ')));
  if(color.cmyk_text)body.append(el('p','原印刷记法：'+color.cmyk_text));
  if(color.archive_member)body.append(el('p','包内依据：'+(color.archive_member_display || color.archive_member)));
  if(color.pantone)body.append(el('p','Pantone '+color.pantone));
  if(valid)body.append(button('复制 HEX',()=>copy(color.value),'quiet'));
  body.append(entries.length>1?sourceCollection(entries,`查看全部配色依据 · ${entries.length}`,c=>[metadata([['用途',c.role],['取值方式',METHODS[c.method] || c.method],['色值',c.value],['RGB',c.rgb?.join(' / ')]])]):provenance(color));card.append(swatch,body);return card;
}
function renderTemplates(school) {
  const sec=section('templates','模板与视觉文件','按适用范围选择。PPTX结构读取不等于逐页预览；声明字体不代表已安装，模板内部主题色不自动成为学校VI。');
  const entries=school.templates.resources.filter(r=>visible({type:r.category.includes('template')?'template':'visual_file',official:r.official,formats:r.formats.map(f=>f.toUpperCase()),status:r.file_inspection_status || r.download_status || 'indexed_not_fetched'}));
  const presentations=school.templates.inspected_presentations.filter(f=>visible({type:'presentation',official:f.official,formats:['PPTX'],status:'content_inspected'}));
  const attachedFileGroups=groupPresentations(school.templates.inspected_presentations);
  const shownFiles=new Set();
  for(const [key,label] of [['school','学校通用'],['department','院系专用'],['community','社区主题'],['unspecified','适用范围未明确'],['visual','PPT 等视觉文件']]) {
    const group=entries.filter(r=>resourceGroup(r)===key);if(!group.length)continue;
    const block=el('div','','template-group');block.append(el('h4',label));
    for(const resourceSet of groupResources(group)) {
      const records=resourceSet.entries,resource=records[0];
      const card=el('div','','template-card');card.append(el('h5',resource.title));const chips=el('div','','chips');chips.append(chip(resource.official?'校方发布':'社区来源',resource.official?'official':'reference'),chip(resource.formats.join(' / ')));card.append(chips);
      card.append(metadata([['来源方',resource.official ? resource.publisher : resource.repository || (resource.publisher===school.name_zh?'社区索引，发布方见来源':resource.publisher)],['版本年份',resource.edition_year],['访问条件',resource.access_requirement],
        ['已读内容',resource.content_read?'原网页 / 文件曾读取':'文件尚未读取'],['读取结果',ACCESS[resource.file_inspection_status || resource.download_status] || resource.download_status]]));
      const links=el('div','','small-links');links.append(link('资源入口 ↗',resource.url),link('发布来源 ↗',resource.source));card.append(links);
      // Read files stay visible under their source entry, independently of declared file labels.
      const files=attachedFileGroups.filter(g=>g.entries.some(f=>records.some(r=>f.url===r.url && f.source===r.source)));
      for(const fileSet of files)if(!shownFiles.has(fileSet.key)){shownFiles.add(fileSet.key);card.append(presentationCard(fileSet));}
      card.append(records.length>1?sourceCollection(records,`同一资源的全部记录 · ${records.length}`,r=>[metadata([['资源名称',r.title],['适用范围',r.use_scope],['版本年份',r.edition_year],['来源属性',r.official?'校方发布':'社区来源'],['格式',r.formats.join(' / ')]]),link('资源入口 ↗',r.url)]):provenance(resource));block.append(card);
    }sec.append(block);
  }
  if(presentations.length && (!entries.length || filters().type==='presentation')) {const groups=groupPresentations(presentations),block=el('div','','template-group');block.append(el('h4',`已读取 PPTX · ${groups.length} 个文件`));for(const group of groups)if(!shownFiles.has(group.key)){shownFiles.add(group.key);block.append(presentationCard(group));}if(block.children.length>1)sec.append(block);}
  if(!entries.length && !presentations.length)sec.append(el('p',school.templates.resources.length?'当前素材条件下没有模板记录；可减少筛选条件。':'本校暂无模板 / PPT 视觉资源记录。官方入口调查状态：'+(availability[school.templates.official_lookup.availability] || '已有入口')+'。','empty'),provenance(school.templates.official_lookup));
  return sec;
}
function presentationCard(group) {
  const file=group.entries.find(f=>!f.archive_member) || group.entries[0];
  const card=el('div','','file-card');card.append(el('h6',file.archive_member || file.title));
  card.append(el('p',`PPTX · ${file.slide_count} 页 · ${file.aspect_ratio} · ${formatSize(file.byte_size)}`),
    el('p','文件结构已读取；幻灯片画面尚未渲染。'),el('p','声明字体：'+(file.font_names.join('、') || '未记录')),
    el('p',`非空文本节点 ${file.editable_text_runs ?? '未记录'}；不保证所有元素可编辑。`));
  if(file.archive_member)card.append(el('p','压缩包成员：'+file.archive_member));
  if(file.theme_colors.length)card.append(el('p','模板内部色值：'+file.theme_colors.join(' / ')));
  card.append(link(file.archive_member?'原压缩包 ↗':'原PPTX入口 ↗',file.download_url),group.entries.length>1?sourceCollection(group.entries,`相同文件的全部来源 · ${group.entries.length}`,f=>[el('p',f.archive_member || f.title),link('原文件 / 原包 ↗',f.download_url)]):provenance(file));return card;
}
function renderContent(school) {
  const sec=section('content','介绍与引用','短简介、校训与建校年份保留来源和历史起点。采集日期不等于原资料的统计或发表日期。');
  for(const [key,label] of [['summary_zh','短简介'],['motto','校训'],['founded_year','建校年份']]) {
    const fact=school.content[key];const item=el('div','','content-item');item.append(el('h4',label),
      el('div',fact.availability==='found'?fact.value:availability[fact.availability] || fact.availability,'content-value'),provenance(fact));sec.append(item);
  }
  for(const [key,label] of [['name_en','英文名（按来源时期）'],['aliases','检索别名（按来源时期）']]) {const fact=school.identity[key];if(fact.availability==='found'){const item=el('div','','content-item');item.append(el('h4',label),el('div',Array.isArray(fact.value)?fact.value.join('、'):fact.value,'content-value'),provenance(fact));sec.append(item);}}
  const identity=el('div','','content-item');identity.append(el('h4','官网与学校身份来源'),provenance(school.identity.official_website));
  const source=el('p');source.append('教育部范围来源：',link('官方名单 ↗',school.registry_source));identity.append(source);sec.append(identity);return sec;
}
async function initialize() {
  try {
    if(['localhost','127.0.0.1','[::1]'].includes(location.hostname)) {
      try {const cache=await fetch('../tmp/viewer-previews/index.json',{cache:'no-store'});if(cache.ok){const data=await cache.json();if(data.cache_version===1)state.localFiles=data.files || {};}}catch {}
    }
    const response=await fetch('data/catalog.json');if(!response.ok)throw new Error('Catalog request failed');
    state.catalog=await response.json();
    const formats=state.catalog.formats.filter(value=>!['HTML','HTML/未知','PPTX示例','未知（未读取目标）'].includes(value));
    for(const [key,values,label] of [['province',state.catalog.provinces,v=>v],['format',formats,v=>({'LATEX/BEAMER':'LaTeX / Beamer','MARKDOWN/MARP':'Markdown / Marp'}[v] || v)]])
      for(const value of values){const option=el('option',label(value));option.value=value;$(key).append(option);}
    const totals=$('totals');totals.replaceChildren();
    for(const [number,label] of [[state.catalog.school_count,'所本科院校'],[state.catalog.schools.filter(s=>s.inspected_logo_count).length,'所已读取标识'],[state.catalog.schools.reduce((n,s)=>n+s.presentation_count,0),'份PPTX结构记录']]){const span=el('span');span.append(el('strong',number.toLocaleString()),label);totals.append(span);}
    const code=new URL(location.href).searchParams.get('school');
    restoreFilters();refreshResults(false);if(code)await selectSchool(code,false);else welcome();
    writeUrl();
  } catch { $('totals').textContent='检索目录载入失败';$('result-count').textContent='请先启动本地HTTP服务';
    $('detail').replaceChildren(el('p',location.protocol==='file:'?'请通过本地HTTP地址打开目录。运行 python3 -m http.server 8765 --bind 127.0.0.1，然后访问 http://127.0.0.1:8765/viewer/。':'目录载入失败，请确认服务目录为资料库根目录，并已生成 viewer/data。','empty'),button('重新载入',()=>location.reload())); }
}
$('filters').addEventListener('submit',event=>event.preventDefault());
let debounce;$('query').addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(()=>refreshResults(),130);});
$('filters').addEventListener('change',event=>{if(event.target.id!=='query')refreshResults();});
$('filters').addEventListener('reset',()=>setTimeout(()=>{clearTimeout(debounce);state.selected=null;state.loadId++;document.querySelector('.advanced').open=false;refreshResults();welcome();},0));
$('prev').addEventListener('click',()=>{state.page--;renderList();$('school-list').scrollTop=0;});
$('next').addEventListener('click',()=>{state.page++;renderList();$('school-list').scrollTop=0;});
window.addEventListener('popstate',()=>{if(!state.catalog)return;const code=new URL(location.href).searchParams.get('school');state.selected=null;state.loadId++;restoreFilters();refreshResults(false);if(code)selectSchool(code,false);else welcome();});
window.addEventListener('hashchange',()=>syncSectionNavigation());
installDisclosureMotion();
initialize();
