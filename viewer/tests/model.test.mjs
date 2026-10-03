import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {matchesSchool,previewMode,previewBackground,resourceGroup,safeUrl,groupLogoAssets,groupColors,
  groupResources,groupPresentations,previewSources} from '../model.mjs';
const catalog=JSON.parse(readFileSync(new URL('../data/catalog.json',import.meta.url)));
const school={school_code:'4111010003',name_zh:'清华大学',province:'北京市',city:'北京市',
  search_names:['Tsinghua University','清华'],scope_tags:['double_first'],color_status:'official_vi',
  materials:[{type:'logo',official:true,formats:['PNG'],kind:'site_identity',status:'content_inspected',transparent:true},
    {type:'logo',official:false,formats:['SVG'],kind:'badge',status:'indexed_not_fetched',transparent:null}]};
test('name, sourced aliases and full-width identity find one school',()=>{
  for(const query of ['清华','tsinghua UNIVERSITY','４１１１０１０００３','北京 清华'])assert.equal(matchesSchool(school,{query}),true);
  assert.equal(matchesSchool(school,{query:'同名独立学院'}),false);
});
test('source and format must match the same material, not different candidates',()=>{
  assert.equal(matchesSchool(school,{source:'official',format:'SVG'}),false);
  assert.equal(matchesSchool(school,{source:'reference',format:'SVG',kind:'badge'}),true);
});
test('unknown transparency is not false or true',()=>{
  assert.equal(matchesSchool(school,{transparent:'unknown',format:'SVG'}),true);
  assert.equal(matchesSchool(school,{transparent:'no'}),false);
});
test('default includes schools with no assets, active material filter excludes them',()=>{
  const empty={...school,materials:[]};assert.equal(matchesSchool(empty,{}),true);
  assert.equal(matchesSchool(empty,{type:'logo'}),false);
});
test('province, tags and screen status are exact identity filters',()=>{
  assert.equal(matchesSchool(school,{province:'北京市',tag:'double_first',colorStatus:'official_vi'}),true);
  for(const filters of [{province:'河北省'},{tag:'private'},{colorStatus:'official_print_only'}])assert.equal(matchesSchool(school,filters),false);
});
test('archive member never becomes a direct PNG preview',()=>{
  assert.equal(previewMode({download_kind:'archive_member',format:'png',url:'https://example.edu/logo.zip',access_status:'content_inspected'}),'archive');
});
test('PDF page mark opens its document and never tries an image preview',()=>{
  const asset={download_kind:'document_page',format:'pdf',url:'https://example.edu/brochure.pdf',access_status:'content_inspected'};
  assert.equal(previewMode(asset),'document');
  assert.equal(previewMode({...asset,url:'javascript:alert(1)'}),'no_url');
});
test('history read success and current browser preview are separate states',()=>{
  const asset={format:'svg',url:'https://example.edu/logo.svg',access_status:'content_inspected'};
  assert.equal(previewMode(asset),'auto');assert.equal(previewMode({...asset,access_status:'inspection_failed'}),'manual');
  assert.equal(previewMode({...asset,format:'pdf'}),'unsupported');
});
test('white preview hint does not depend on school primary color',()=>{
  const asset={preview_background_hint:{value:'dark'}};
  assert.equal(previewBackground(asset),'dark');assert.equal(previewBackground(asset,'light'),'light');
  assert.equal(previewBackground({}),'light');
  assert.equal(previewBackground({kind:'site_identity',transparent_background:true}),'dark');
  assert.equal(previewBackground({kind:'site_identity',transparent_background:true,preview_background_hint:{value:'light'}}),'light');
});
test('unsafe links cannot become browser navigation or image URLs',()=>{
  for(const url of ['javascript:alert(1)','data:text/html,x','https://user:secret@example.edu/'])assert.equal(safeUrl(url),null);
  assert.equal(safeUrl('https://example.edu/vi'),'https://example.edu/vi');
});
test('PPTX containing a logo is a visual file, not a template',()=>{
  assert.equal(resourceGroup({category:'official_visual_resource',use_scope:'school'}),'visual');
  assert.equal(resourceGroup({category:'official_template',use_scope:'department'}),'department');
});
test('generated catalog has all unique identities and all declared region bundles',()=>{
  assert.equal(catalog.schools.length,1412);assert.equal(new Set(catalog.schools.map(s=>s.school_code)).size,1412);
  for(const province of catalog.provinces){const bundle=JSON.parse(readFileSync(new URL(`../data/provinces/${province}.json`,import.meta.url)));
    for(const entry of Object.values(bundle.schools))assert.equal(entry.province,province);}
});
test('real print-only and conflict cases retain empty screen choice',()=>{
  for(const province of catalog.provinces){const bundle=JSON.parse(readFileSync(new URL(`../data/provinces/${province}.json`,import.meta.url)));
    for(const entry of Object.values(bundle.schools))if(['conflict','official_print_only'].includes(entry.colors.screen_status))assert.equal(entry.colors.screen_primary,null);}
});
test('same logo file keeps all sources in one version and different files stay selectable',()=>{
  const a={kind:'badge',sha256:'a'.repeat(64),url:'https://a.edu/logo.png'},b={...a,url:'https://b.edu/logo.png'},c={...a,sha256:'b'.repeat(64)};
  const groups=groupLogoAssets([a,b,c]);assert.equal(groups.length,1);assert.equal(groups[0].versions.length,2);
  assert.deepEqual(groups[0].versions[0].entries,[a,b]);
  const raw={...a,sha256:null};assert.equal(groupLogoAssets([a,raw])[0].versions.length,1);
  assert.equal(groupLogoAssets([a,c,raw])[0].versions.length,3,'URL with two known hashes must not guess an unread version');
});
test('ZIP members and PDF regions are separate versions of their container',()=>{
  const zip={kind:'badge',download_kind:'archive_member',url:'https://a.edu/logos.zip'};
  assert.equal(groupLogoAssets([{...zip,archive_member:'1.png'},{...zip,archive_member:'2.png'}])[0].versions.length,2);
  const pdf={kind:'combination',download_kind:'document_page',sha256:'c'.repeat(64),document_page:1};
  assert.equal(groupLogoAssets([{...pdf,document_mark_region:[0,0,10,10]},{...pdf,document_mark_region:[20,20,30,30]}])[0].versions.length,2);
});
test('unknown locations stay separate and original records are not mutated',()=>{
  const records=[{kind:'badge',title:'a'},{kind:'badge',title:'b'}],before=JSON.stringify(records);
  assert.equal(groupLogoAssets(records)[0].versions.length,2);assert.equal(JSON.stringify(records),before);
});
test('equal colors combine sources while RGB conflicts and different print colors remain',()=>{
  const a={value:'#ffffff',label:'a',role:'primary'},b={value:'#FFFFFF',rgb:[255,255,255],label:'b',role:'secondary'};
  assert.deepEqual(groupColors([a,b])[0].entries,[a,b]);
  assert.equal(groupColors([a,{...b,rgb:[254,255,255]}]).length,2);
  assert.equal(groupColors([{cmyk:[1,2,3,4]},{cmyk:[1,2,3,5]}]).length,2);
  assert.equal(groupColors([{value:null},{value:null}]).length,2);
});
test('resource grouping keeps different use scopes and editions separate',()=>{
  const r={url:'https://a.edu/theme',category:'official_template',use_scope:'school'};
  assert.equal(groupResources([r,{...r,source:'https://b.edu/index'}]).length,1);
  assert.equal(groupResources([r,{...r,use_scope:'department'},{...r,edition_year:2025}]).length,3);
  assert.equal(groupResources([{...r,url:null},{...r,url:null}]).length,2);
  assert.equal(groupPresentations([{sha256:'a'.repeat(64)},{sha256:'a'.repeat(64)}]).length,1);
});
test('local archive previews use only the inspected image hash, never the ZIP or PDF as an image',()=>{
  const sha='d'.repeat(64),a={sha256:sha,format:'png',url:'https://a.edu/logos.zip',download_kind:'archive_member'};
  assert.deepEqual(previewSources([a],{[sha]:{format:'png'}}),[{url:`../tmp/viewer-previews/${sha}.png`,local:true}]);
  assert.deepEqual(previewSources([{...a,download_kind:'document_page',format:'pdf'}],{[sha]:{format:'pdf'}}),[]);
  assert.deepEqual(previewSources([{format:'png',url:'javascript:alert(1)'}]),[]);
});
test('real school views retain every source entry while consolidating the visual families',()=>{
  const bundle=JSON.parse(readFileSync(new URL('../data/provinces/北京市.json',import.meta.url)));
  const pku=bundle.schools['4111010001'],families=groupLogoAssets(pku.logos.candidates);
  assert.equal(families.length,3);assert.equal(families.flatMap(f=>f.versions.flatMap(v=>v.entries)).length,pku.logos.candidates.length);
  assert.ok(groupColors(pku.colors.references).length<pku.colors.references.length);
});
