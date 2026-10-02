import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {matchesSchool,previewMode,previewBackground,resourceGroup,safeUrl} from '../model.mjs';
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
test('history read success and current browser preview are separate states',()=>{
  const asset={format:'svg',url:'https://example.edu/logo.svg',access_status:'content_inspected'};
  assert.equal(previewMode(asset),'auto');assert.equal(previewMode({...asset,access_status:'inspection_failed'}),'manual');
  assert.equal(previewMode({...asset,format:'pdf'}),'unsupported');
});
test('white preview hint does not depend on school primary color',()=>{
  const asset={preview_background_hint:{value:'dark'}};
  assert.equal(previewBackground(asset),'dark');assert.equal(previewBackground(asset,'light'),'light');
  assert.equal(previewBackground({}),'light');
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
