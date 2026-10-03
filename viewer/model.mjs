export const TAGS = {double_first:'双一流', vocational_undergraduate:'职业本科', private:'民办',
  cooperative:'合作办学', all_undergraduate:'全量本科', name_ends_university:'校名以大学结尾',
  short_name:'短校名', moe_note_blank:'教育部备注为空', hainan_education_institution:'海南教育机构'};
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
  return asset.preview_background_hint?.value === 'dark' ? 'dark' : 'light';
}
export function resourceGroup(resource) {
  if (!resource.category.includes('template')) return 'visual';
  return resource.use_scope || 'unspecified';
}
export function formatSize(bytes) {
  if (!Number.isFinite(bytes)) return '未记录';
  return bytes < 1024 ? `${bytes} B` : bytes < 1024*1024 ? `${(bytes/1024).toFixed(1)} KB` : `${(bytes/1024/1024).toFixed(1)} MB`;
}
