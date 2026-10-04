// Only school attributes intended for display; collection tags stay in the data.
export const TAGS = {double_first:'双一流', vocational_undergraduate:'职业本科', private:'民办', cooperative:'合作办学'};
export const KINDS = {badge:'纯校徽', wordmark:'校名文字', combination:'徽名组合',
  site_identity:'官网页眉标识（构成待核验）', anniversary:'纪念标识'};
export const COLOR_STATUS = {official_vi:'官方数字主色', official_print_only:'主色仅有印刷值',
  design_reference:'设计参考主色', conflict:'主色来源冲突', unresearched:'主色待调查', not_found:'已检索未找到主色'};
export const ACCESS = {content_inspected:'内容已读取', indexed_not_fetched:'仅有入口，未读取文件',
  inspection_failed:'历史读取失败', target_page_read:'实际目标为网页', format_only:'仅识别文件格式',
  page_read:'发布网页已读取', source_text_read:'源码文本已读', downloaded_format_only:'仅识别文件格式'};
export const METHODS = {official_vi:'校方VI数字证据', badge_sample:'标识取色参考', manual_derived:'设计参考',
  community_theme:'社区主题参考', community_logo_sample:'社区标识取色参考'};
export function safeUrl(value) {
  if (typeof value !== 'string') return null;
  try {const u = new URL(value); return ['https:','http:'].includes(u.protocol) && !u.username && !u.password ? u.href : null;}
  catch {return null;}
}
export function materialMatches(m, f={}) {
  if (f.type && f.type !== 'all' && m.type !== f.type) return false;
  if (f.source === 'official' && m.official !== true) return false;
  if (f.source === 'reference' && m.official !== false) return false;
  if (f.format && !m.formats?.includes(f.format.toUpperCase())) return false;
  if (f.kind && m.kind !== f.kind) return false;
  if (f.transparent === 'yes' && m.transparent !== true) return false;
  if (f.transparent === 'no' && m.transparent !== false) return false;
  if (f.transparent === 'unknown' && (m.type !== 'logo' || m.transparent != null)) return false;
  if (f.status && m.status !== f.status) return false;
  return true;
}
export function matchesSchool(school, f={}) {
  const normalize = s => String(s).normalize('NFKC').toLowerCase();
  const tokens = normalize(f.query || '').trim().split(/\s+/).filter(Boolean);
  const hay = normalize([school.name_zh,school.school_code,school.province,school.city,...school.search_names].join(' '));
  if (!tokens.every(t => hay.includes(t))) return false;
  if (f.province && school.province !== f.province) return false;
  if (f.tag && !school.scope_tags.includes(f.tag)) return false;
  if (f.colorStatus && school.color_status !== f.colorStatus) return false;
  const active = (f.type && f.type !== 'all') || f.source || f.format || f.kind || f.transparent || f.status;
  return !active || school.materials.some(m => materialMatches(m,f));
}
export function previewMode(asset) {
  if (asset.download_kind === 'archive_member') return 'archive';
  if (!safeUrl(asset.resolved_url || asset.url)) return 'no_url';
  if (asset.download_kind === 'document_page' && String(asset.format || '').toLowerCase() === 'pdf') return 'document';
  if (!['svg','png','jpeg','jpg','gif','webp','bmp','ico','avif'].includes(String(asset.format || '').toLowerCase())) return 'unsupported';
  return asset.access_status === 'content_inspected' ? 'auto' : 'manual';
}
export function previewBackground(asset, choice='auto') {
  if (choice !== 'auto') return choice;
  const hint=asset.preview_background_hint?.value;
  if(['dark','light'].includes(hint))return hint;
  return asset.transparent_background===true && ['site_identity','wordmark'].includes(asset.kind)?'dark':'light';
}
export function resourceGroup(resource) {
  if (!resource.category.includes('template')) return 'visual';
  return resource.use_scope || 'unspecified';
}
export function formatSize(bytes) {
  if (!Number.isFinite(bytes)) return '未记录';
  return bytes < 1024 ? `${bytes} B` : bytes < 1024*1024 ? `${(bytes/1024).toFixed(1)} KB` : `${(bytes/1024/1024).toFixed(1)} MB`;
}

const SHA = /^[a-f0-9]{64}$/i;
const IMAGE_FORMATS = new Set(['svg','png','jpeg','jpg','gif','webp','bmp','ico','avif']);
function fileLocation(entry) {
  const url = safeUrl(entry.resolved_url || entry.url || entry.download_url);
  if (!url) return '';
  const u = new URL(url); u.hash='';
  return u.href + (entry.archive_member ? `|member:${entry.archive_member}` : '');
}
function fileIdentity(entry, index) {
  const hash=SHA.test(entry.sha256 || '')?entry.sha256.toLowerCase():'';
  if(!hash && !fileLocation(entry))return `record:${index}`;
  if (entry.download_kind==='document_page') return JSON.stringify(['document',hash || fileLocation(entry),
    entry.document_page,entry.document_image_index,entry.document_image_sha256,entry.document_mark_region]);
  return hash?`sha:${hash}`:fileLocation(entry)?`url:${fileLocation(entry)}`:`record:${index}`;
}
function fileGroups(entries) {
  const hashes=new Map();
  for(const entry of entries) {
    const location=fileLocation(entry);
    if(location && SHA.test(entry.sha256 || '') && entry.download_kind!=='document_page') {
      if(!hashes.has(location))hashes.set(location,new Set());hashes.get(location).add(entry.sha256.toLowerCase());
    }
  }
  return grouped(entries,(entry,index)=>{
    const known=hashes.get(fileLocation(entry));
    if(!SHA.test(entry.sha256 || '') && entry.download_kind!=='document_page' && known?.size===1)return `sha:${[...known][0]}`;
    return fileIdentity(entry,index);
  });
}
function grouped(entries, keyOf) {
  const groups=new Map();
  entries.forEach((entry,index)=>{const key=keyOf(entry,index);if(!groups.has(key))groups.set(key,{key,entries:[]});groups.get(key).entries.push(entry);});
  return [...groups.values()];
}
export function groupLogoAssets(assets) {
  // Same bytes share sources; different files remain selectable versions within their type.
  const versions=fileGroups(assets);
  const families=new Map();
  for(const version of versions) {
    const kinds=[...new Set(version.entries.map(a=>a.kind))].sort();
    const kind=kinds.length===1?kinds[0]:'mixed';
    const key=kind==='mixed'?`mixed:${version.key}`:kind;
    if(!families.has(key))families.set(key,{key,kind,versions:[]});
    families.get(key).versions.push(version);
  }
  return [...families.values()];
}
export function groupColors(colors) {
  return grouped(colors,(c,index)=>{
    const hex=/^#[a-f0-9]{6}$/i.test(c.value || '')?c.value.toUpperCase():null;
    const rgb=c.rgb || (hex?[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)):null);
    if(!hex && !c.cmyk && !c.cmyk_text && !c.pantone)return `record:${index}`;
    // Inconsistent RGB, print notations and Pantone are not discarded as duplicate HEX.
    return JSON.stringify([hex,rgb,c.cmyk || null,c.cmyk_text || null,c.pantone || null]);
  });
}
export function groupResources(resources) {
  return grouped(resources,(r,index)=>{
    const url=safeUrl(r.url);
    return url?JSON.stringify([url,resourceGroup(r),r.edition_year || null]):`record:${index}`;
  });
}
export function groupPresentations(files) {return fileGroups(files);}
export function previewSources(entries, localFiles={}) {
  const sources=[];const seen=new Set();
  const add=(url,local)=>{if(url && !seen.has(url)){seen.add(url);sources.push({url,local});}};
  for(const a of entries) {
    const sha=(a.sha256 || '').toLowerCase(), cached=localFiles[sha];
    if(a.download_kind!=='document_page' && SHA.test(sha) && cached && IMAGE_FORMATS.has(cached.format)
      && cached.format===String(a.format || '').toLowerCase())add(`../tmp/viewer-previews/${sha}.${cached.format}`,true);
  }
  for(const a of entries)if(['auto','manual'].includes(previewMode(a))) {
    add(safeUrl(a.resolved_url || a.url),false);add(safeUrl(a.url),false);
  }
  return sources;
}
