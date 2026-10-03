import {TAGS,KINDS,COLOR_STATUS,ACCESS,METHODS,safeUrl,matchesSchool,materialMatches,
  previewMode,previewBackground,resourceGroup,formatSize} from './model.mjs';

const $ = id => document.getElementById(id);
const PAGE_SIZE = 24;
const fields = ['query','province','tag','type','source','format','kind','transparent','status','colorStatus'];
const state = {catalog:null,selected:null,page:0,rows:[],loadId:0,bundles:new Map(),background:'auto'};
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
}
function updateFilterControls() {
  const type=$('type').value;
  for (const key of ['kind','transparent']) {$(key).disabled=!['all','logo'].includes(type); if ($(key).disabled) $(key).value='';}
  for (const key of ['format','status']) {$(key).disabled=type==='color'; if ($(key).disabled) $(key).value='';}
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
  $('result-count').textContent=`${state.rows.length.toLocaleString()} 所匹配学校 / ${state.catalog.school_count.toLocaleString()} 所本科院校`;
  const list=$('school-list'); list.replaceChildren();
  if (!state.rows.length) list.append(el('p','暂无匹配学校。可减少素材条件或重置筛选。','empty'));
  for (const school of state.rows.slice(state.page*PAGE_SIZE,(state.page+1)*PAGE_SIZE)) {
    const card=button('',()=>selectSchool(school.school_code),'school-card'+(state.selected?.school_code===school.school_code?' selected':''));
    card.setAttribute('aria-label',`查看${school.name_zh}资料`); card.append(el('h3',school.name_zh),el('div',`${school.province} · ${school.school_code}`,'school-meta'));
    const counts=el('div','','school-counts');
    counts.append(el('span',`标识 ${school.logo_count}`),el('span',`色卡 ${school.color_count}`),el('span',`模板 ${school.template_count}`));
    card.append(counts,el('div',COLOR_STATUS[school.color_status],'school-status')); list.append(card);
  }
  $('page-info').textContent=state.rows.length?`${state.page+1} / ${pages}`:'0 / 0';
  $('prev').disabled=state.page===0; $('next').disabled=!state.rows.length || state.page>=pages-1;
}
function welcome() {
  const node=el('div','','welcome'); node.append(el('span','从学校开始','section-kicker'),el('h2','让资料成为你的下一页 PPT。'),
    el('p','选择学校后，逐项查看标识文件、配色方法、模板格式和来源。未找到资料与预览失败会分别显示。'));
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
    if(matchMedia('(max-width:760px)').matches)$('detail').scrollIntoView({behavior:'smooth',block:'start'});
  } catch {if(loadId!==state.loadId)return;
    $('detail').replaceChildren(el('p','单校资料载入失败。已取得的检索目录仍可使用。','empty'),button('重新载入',()=>selectSchool(code,push)));}
}
function visible(descriptor) {return materialMatches(descriptor,filters());}
function renderSchool(school) {
  const header=el('header','','detail-header'); header.append(el('div',`${school.province} / ${school.city} / ${school.school_code}`,'breadcrumb'),el('h2',school.name_zh));
  const tags=el('div','','tags'); for(const tag of school.scope_tags) if(['double_first','private','cooperative','vocational_undergraduate'].includes(tag))tags.append(el('span',TAGS[tag] || tag,'tag'));header.append(tags);
  const actions=el('div','','actions');const site=school.identity.official_website;
  if(site.availability==='found')actions.append(link('学校官网 ↗',site.value,'button'));
  else actions.append(chip(`官网：${availability[site.availability] || site.availability}`));
  actions.append(button('复制该校资料',()=>copy(JSON.stringify(school,null,2))),button('下载单校 JSON',()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(school,null,2)+'\n'],{type:'application/json'}));
    const a=el('a');a.href=url;a.download=`${school.school_code}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }));
  if(/^universities\/[^/]+\/\d{10}\/profile\.yaml$/.test(school.profile_path)) {const a=el('a','完整档案','button');a.href='../'+school.profile_path;actions.append(a);}
  header.append(actions);
  const jsonDetails=el('details','','source-details');jsonDetails.append(el('summary','查看 / 手动复制单校 JSON'));
  const jsonText=el('textarea','','json-data');jsonText.readOnly=true;jsonText.rows=8;
  jsonText.setAttribute('aria-label','单校 JSON 资料');jsonText.value=JSON.stringify(school,null,2);
  jsonDetails.append(jsonText);header.append(jsonDetails);
  const nav=el('nav','','subnav');nav.setAttribute('aria-label','单校资料分区');
  for(const [id,label] of [['logos','标识'],['colors','配色'],['templates','模板'],['content','介绍']]) {const a=el('a',label);a.href='#'+id;nav.append(a);}
  $('detail').replaceChildren(header,nav,renderLogos(school),renderColors(school),renderTemplates(school),renderContent(school));
}
function renderLogos(school) {
  const sec=section('logos',`标识 · ${school.logos.candidates.length} 个记录`,'网页预览与历史文件读取分别记账。预览背景便于辨认图形，不代表学校标准色或VI背景规则。');
  const choice=el('label','预览背景 ','background-choice');const select=el('select'); select.setAttribute('aria-label','标识预览背景');
  for(const [value,label] of [['auto','按标签自动'],['light','浅色'],['dark','深色'],['checker','透明棋盘']]) {const opt=el('option',label);opt.value=value;select.append(opt);}select.value=state.background;
  select.addEventListener('change',()=>{state.background=select.value; sec.querySelectorAll('.asset-preview').forEach(box=>{box.dataset.background=previewBackground(JSON.parse(box.dataset.assetHint),state.background);});});
  choice.append(select);sec.querySelector('.section-title').append(choice);
  if (school.logos.candidates.length) sec.append(el('p',school.logos.reason,'callout'));
  const grid=el('div','','logo-grid');const assets=school.logos.candidates.filter(a=>visible({type:'logo',official:a.official,formats:a.format?[a.format.toUpperCase()]:[],kind:a.kind,transparent:a.transparent_background,status:a.access_status}));
  for(const asset of assets) grid.append(logoCard(asset,school.logos.recommended_asset_id));sec.append(grid);
  if(!assets.length) sec.append(el('p',school.logos.candidates.length?'当前素材条件下没有标识记录；可清除条件查看全部候选。':'逐文件标识集合为空。官网或VI调查状态见下方，不能推断学校没有标识。','empty'));
  if(!school.logos.candidates.length)for(const [key,label] of [['vi_url','VI入口'],['badge_description','标识简述']]) {const fact=school.logos.lookup_status[key];sec.append(el('p',`${label}：${availability[fact.availability] || '已记录'}`,'section-desc'),provenance(fact));}
  return sec;
}
function logoCard(asset,recommended) {
  const card=el('div','','asset-card');card.dataset.assetId=asset.asset_id;
  const box=el('div','','asset-preview');box.dataset.background=previewBackground(asset,state.background);
  box.dataset.assetHint=JSON.stringify({preview_background_hint:asset.preview_background_hint});
  const mode=previewMode(asset);const placeholder=el('div','','preview-placeholder');box.append(placeholder);
  const body=el('div','','asset-body');body.append(el('h4',asset.variant || asset.title));
  const chips=el('div','','chips');chips.append(chip(KINDS[asset.kind] || asset.kind),chip(asset.official?'校方发布':'社区来源',asset.official?'official':'reference'));
  if(asset.asset_id===recommended)chips.append(chip('目录推荐','official'));body.append(chips);
  const previewStatus=el('div','网页预览：尚未载入','preview-status');body.append(previewStatus);
  function startImage() {
    placeholder.textContent='正在载入原来源图形…';
    const img=el('img');img.alt=asset.title;img.decoding='async';img.referrerPolicy='no-referrer';
    let finished=false;
    const timeout=setTimeout(()=>{if(finished)return;finished=true;img.onload=null;img.onerror=null;img.remove();placeholder.textContent='本次网页预览超时；原来源入口仍可查阅。';previewStatus.textContent='网页预览：本次未完成';placeholder.append(button('重试',startImage,'quiet'));},12000);
    img.onload=()=>{if(finished)return;finished=true;clearTimeout(timeout);placeholder.remove();previewStatus.textContent='网页预览：本次已载入图形';};
    img.onerror=()=>{if(finished)return;finished=true;clearTimeout(timeout);img.remove();placeholder.textContent='本次网页预览失败；历史读取记录保持独立。';previewStatus.textContent='网页预览：本次载入失败';placeholder.append(button('重试',startImage,'quiet'));};
    if(!placeholder.isConnected)box.append(placeholder);
    box.append(img);img.src=safeUrl(asset.resolved_url || asset.url);
  }
  if(mode==='auto') {placeholder.textContent='等待载入图形';setTimeout(()=>{if(card.isConnected)startImage();},0);}
  else if(mode==='manual'){placeholder.textContent='文件尚未成功读取；可尝试网页预览。';placeholder.append(button('尝试载入图形',startImage,'quiet'));}
  else {placeholder.textContent=mode==='archive'?'ZIP 压缩包成员\n使用下方原包入口和成员路径获取':mode==='document'?`公开 PDF 第 ${asset.document_page} 页中的标识\n请从下方原 PDF 获取`:mode==='unsupported'?'此格式未提供网页图形预览':'暂无可用的图形网址'; previewStatus.textContent='网页预览：未提供直接图像预览';}
  const yesNo=v=>v===true?'是':v===false?'否':'未记录';
  body.append(metadata([['文件读取',ACCESS[asset.access_status] || asset.access_status],['格式',asset.format?.toUpperCase()],
    ['尺寸',asset.width && asset.height?`${asset.width} × ${asset.height}`:'未记录完整实测尺寸'],['矢量表示',yesNo(asset.vector)],
    ['透明背景',yesNo(asset.transparent_background)],['版式/文件',asset.file_name],
    ...(asset.archive_member?[['包内路径',asset.archive_member_display || asset.archive_member]]:[]),
    ...(mode==='document'?[['PDF页码',`${asset.document_page} / ${asset.document_page_count}`]]:[])]));
  if(mode==='document')body.append(el('p',asset.usage_note,'section-desc'));
  if(asset.archive_member_display && asset.archive_member_display!==asset.archive_member)body.append(el('p','可读路径已恢复中文编码；程序读取请使用复制资料中的 archive_member 原值。','section-desc'));
  if(asset.preview_background_hint)body.append(el('p',asset.preview_background_hint.basis,'section-desc'));
  const links=el('div','','small-links');links.append(link(mode==='archive'?'原压缩包 ↗':mode==='document'?'原 PDF ↗':'原文件 ↗',asset.archive_url || asset.url),link('发布来源 ↗',asset.source));body.append(links,provenance(asset));card.append(box,body);return card;
}
function renderColors(school) {
  const colors=school.colors;const sec=section('colors','配色证据','官方数字色、印刷色与设计参考分开显示。CMYK/Pantone没有数字屏幕值时，不自动换算HEX。');
  sec.append(el('p',`${COLOR_STATUS[colors.screen_status]} · ${colors.reason}`,colors.screen_status==='conflict'?'callout warning':'callout'));
  if(colors.screen_primary){const selected=el('div','','actions');selected.append(el('span',`当前屏幕选择 ${colors.screen_primary.value}`,'hex'),button('复制色值',()=>copy(colors.screen_primary.value),'quiet'));sec.append(selected,provenance(colors.screen_primary));}
  for(const conflict of colors.conflicts) {
    const block=el('div','','color-section');block.append(el('h4',conflict.field==='visual.color_primary'?'主色来源冲突':'辅色 / 并列色来源冲突'));
    const grid=el('div','','color-grid');for(const c of conflict.fact.candidates)grid.append(colorCard({...c,checked_at:conflict.fact.checked_at,verified:conflict.fact.verified,method:'conflict',basis:c.basis || conflict.fact.note || '保留来源候选，未自动选择。'}));block.append(grid);sec.append(block);
  }
  for(const [key,label] of [['official_digital','校方数字色'],['official_print_only','校方印刷色'],['references','设计与社区参考色']]) {
    const entries=colors[key].filter(c=>visible({type:'color',official:c.method==='official_vi',formats:[],status:c.value==null?'print_only':c.method}));
    if(!entries.length)continue;const block=el('div','','color-section');block.append(el('h4',`${label} · ${entries.length}`));const grid=el('div','','color-grid');for(const c of entries)grid.append(colorCard(c));block.append(grid);sec.append(block);
  }
  if(!['official_digital','official_print_only','references'].some(k=>colors[k].length) && !colors.conflicts.length)sec.append(el('p','结构化配色集合为空。当前调查状态与原主色事实仍保留。','empty'),provenance(colors.primary_fact));
  return sec;
}
function colorCard(color) {
  const card=el('div','','color-card');const valid=/^#[0-9a-f]{6}$/i.test(color.value || '');
  const swatch=el('div',valid?'':'仅印刷证据','swatch'+(valid?'':' print-only'));if(valid)swatch.style.backgroundColor=color.value;
  const body=el('div','','color-body');body.append(el('h5',color.label || {primary:'主色记录',secondary:'辅色 / 并列记录',reference:'参考色',accent:'强调色'}[color.role] || '来源候选'));
  body.append(el('div',valid?color.value:'屏幕值为空','hex'),el('p',!valid && color.method==='official_vi'?'校方VI印刷证据':METHODS[color.method] || '来源存在冲突'));
  if(color.rgb)body.append(el('p','RGB '+color.rgb.join(' / ')));
  if(color.cmyk)body.append(el('p','CMYK '+color.cmyk.join(' / ')));
  if(color.cmyk_text)body.append(el('p','原印刷记法：'+color.cmyk_text));
  if(color.archive_member)body.append(el('p','包内依据：'+(color.archive_member_display || color.archive_member)));
  if(color.pantone)body.append(el('p','Pantone '+color.pantone));
  if(valid)body.append(button('复制 HEX',()=>copy(color.value),'quiet'));
  body.append(provenance(color));card.append(swatch,body);return card;
}
function renderTemplates(school) {
  const sec=section('templates','模板与视觉文件','按适用范围选择。PPTX结构读取不等于逐页预览；声明字体不代表已安装，模板内部主题色不自动成为学校VI。');
  const entries=school.templates.resources.filter(r=>visible({type:r.category.includes('template')?'template':'visual_file',official:r.official,formats:r.formats.map(f=>f.toUpperCase()),status:r.file_inspection_status || r.download_status || 'indexed_not_fetched'}));
  const presentations=school.templates.inspected_presentations.filter(f=>visible({type:'presentation',official:f.official,formats:['PPTX'],status:'content_inspected'}));
  for(const [key,label] of [['school','学校通用'],['department','院系专用'],['community','社区主题'],['unspecified','适用范围未明确'],['visual','PPT 等视觉文件']]) {
    const group=entries.filter(r=>resourceGroup(r)===key);if(!group.length)continue;
    const block=el('div','','template-group');block.append(el('h4',label));
    for(const resource of group) {
      const card=el('div','','template-card');card.append(el('h5',resource.title));const chips=el('div','','chips');chips.append(chip(resource.official?'校方发布':'社区来源',resource.official?'official':'reference'),chip(resource.formats.join(' / ')));card.append(chips);
      card.append(metadata([['来源方',resource.official ? resource.publisher : resource.repository || (resource.publisher===school.name_zh?'社区索引，发布方见来源':resource.publisher)],['版本年份',resource.edition_year],['访问条件',resource.access_requirement],
        ['已读内容',resource.content_read?'原网页 / 文件曾读取':'文件尚未读取'],['读取结果',ACCESS[resource.file_inspection_status || resource.download_status] || resource.download_status]]));
      const links=el('div','','small-links');links.append(link('资源入口 ↗',resource.url),link('发布来源 ↗',resource.source));card.append(links);
      // Read files stay visible under their source entry, independently of declared file labels.
      for(const file of school.templates.inspected_presentations.filter(f=>f.url===resource.url && f.source===resource.source))card.append(presentationCard(file));
      card.append(provenance(resource));block.append(card);
    }sec.append(block);
  }
  if(presentations.length && (!entries.length || filters().type==='presentation')) {const block=el('div','','template-group');block.append(el('h4',`已读取 PPTX · ${presentations.length}`));for(const f of presentations)block.append(presentationCard(f));sec.append(block);}
  if(!entries.length && !presentations.length)sec.append(el('p',school.templates.resources.length?'当前素材条件下没有模板记录；可减少筛选条件。':'本校暂无模板 / PPT 视觉资源记录。官方入口调查状态：'+(availability[school.templates.official_lookup.availability] || '已有入口')+'。','empty'),provenance(school.templates.official_lookup));
  return sec;
}
function presentationCard(file) {
  const card=el('div','','file-card');card.append(el('h6',file.archive_member || file.title));
  card.append(el('p',`PPTX · ${file.slide_count} 页 · ${file.aspect_ratio} · ${formatSize(file.byte_size)}`),
    el('p','文件结构已读取；幻灯片画面尚未渲染。'),el('p','声明字体：'+(file.font_names.join('、') || '未记录')),
    el('p',`非空文本节点 ${file.editable_text_runs ?? '未记录'}；不保证所有元素可编辑。`));
  if(file.archive_member)card.append(el('p','压缩包成员：'+file.archive_member));
  if(file.theme_colors.length)card.append(el('p','模板内部色值：'+file.theme_colors.join(' / ')));
  card.append(link(file.archive_member?'原压缩包 ↗':'原PPTX入口 ↗',file.download_url),provenance(file));return card;
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
    const response=await fetch('data/catalog.json');if(!response.ok)throw new Error('Catalog request failed');
    state.catalog=await response.json();
    for(const [key,values,label] of [['province',state.catalog.provinces,v=>v],['tag',state.catalog.tags,v=>TAGS[v] || v],['format',state.catalog.formats,v=>v]])
      for(const value of values){const option=el('option',label(value));option.value=value;$(key).append(option);}
    const totals=$('totals');totals.replaceChildren();
    for(const [number,label] of [[state.catalog.school_count,'所本科院校'],[state.catalog.schools.filter(s=>s.inspected_logo_count).length,'所已读取标识'],[state.catalog.schools.reduce((n,s)=>n+s.presentation_count,0),'份PPTX结构记录']]){const span=el('span');span.append(el('strong',number.toLocaleString()),label);totals.append(span);}
    restoreFilters();refreshResults(false);const code=new URL(location.href).searchParams.get('school');if(code)await selectSchool(code,false);else welcome();
  } catch { $('totals').textContent='检索目录载入失败';$('result-count').textContent='请先启动本地HTTP服务';
    $('detail').replaceChildren(el('p',location.protocol==='file:'?'请通过本地HTTP地址打开目录。运行 python3 -m http.server 8765 --bind 127.0.0.1，然后访问 http://127.0.0.1:8765/viewer/。':'目录载入失败，请确认服务目录为资料库根目录，并已生成 viewer/data。','empty'),button('重新载入',()=>location.reload())); }
}
$('filters').addEventListener('submit',event=>event.preventDefault());
let debounce;$('query').addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(()=>refreshResults(),130);});
$('filters').addEventListener('change',event=>{if(event.target.id!=='query')refreshResults();});
$('filters').addEventListener('reset',()=>setTimeout(()=>{clearTimeout(debounce);state.selected=null;state.loadId++;refreshResults();welcome();},0));
$('prev').addEventListener('click',()=>{state.page--;renderList();$('school-list').scrollTop=0;});
$('next').addEventListener('click',()=>{state.page++;renderList();$('school-list').scrollTop=0;});
window.addEventListener('popstate',()=>{if(!state.catalog)return;const code=new URL(location.href).searchParams.get('school');state.selected=null;state.loadId++;restoreFilters();refreshResults(false);if(code)selectSchool(code,false);else welcome();});
initialize();
