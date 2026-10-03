"""Shared version 3 field definitions and source-aware migration helpers."""
import copy

SCHEMA_VERSION = 3
# Every scalar/container fact retains the same provenance envelope as v2.
FACTS = {
    'identity.short_name_zh': ('text', '中文简称'),
    'identity.short_name_en': ('text', '英文简称'),
    'identity.aliases': ('text_list', '学校别名及曾用名，需保留时期说明'),
    'identity.slug_aliases': ('text_list', '社区检索标识，不能当作正式校名'),
    'institution.school_type': ('text', '综合、理工、师范等院校类型'),
    'institution.nature': ('text', '公办、民办等办学性质，不从空备注推断'),
    'institution.country': ('text', '所在国家或地区'),
    'institution.languages_of_instruction': ('text_list', '授课语言，社区资料不等于全部专业语言'),
    'institution.groups': ('text_list', '院校群与历史项目标签，非排名'),
    'location.address': ('text', '通讯地址，不能代替全部校区地址'),
    'location.postal_code': ('text', '邮政编码'),
    'location.coordinates': ('coordinates', '经纬度及坐标系、位置精度'),
    'overview.summary_zh': ('text', '中文简介，短摘要'),
    'overview.summary_en': ('text', '英文简介，短摘要'),
    'statistics.student_count': ('number', '学生人数，需统计日期和口径'),
    'statistics.faculty_count': ('number', '教职工人数，需统计日期和口径'),
    'statistics.campus_area_hectares': ('number', '校园面积，公顷，需日期和口径'),
    'academics.double_first_class_disciplines': ('text_list', '双一流建设学科，注明名单年份及是否节选'),
    'academics.degree_authorizations': ('text_list', '学位授权，需年份与层次口径'),
    'employment.summary': ('text', '就业概况，需对应毕业届次'),
    'employment.report_url': ('url', '就业质量报告入口'),
    'resources.admissions_url': ('url', '招生入口'),
    'resources.career_url': ('url', '就业入口'),
    'resources.english_website': ('url', '英文网站入口'),
    'resources.information_disclosure_url': ('url', '信息公开入口'),
    'contacts.phone': ('text', '公开办公或招生电话'),
    'contacts.email': ('text', '公开办公邮箱'),
}
COLLECTIONS = {
    'identity.external_identifiers': '外部平台标识及命名空间',
    'location.campuses': '校区名称、地址和坐标',
    'visual.logo_assets': '逐文件校徽、校名文字及组合标识资源',
    'visual.color_palette': '结构化调色板，区分官方标准与设计参考',
    'visual.vi_resources': 'VI下载页、资源类型、格式与访问限制',
    'academics.subject_assessments': '按评估轮次、学科、等级保存',
    'rankings.entries': '按发布方、榜单、年份、范围保存名次和指标',
    'admissions.cutoffs': '地区、年份、科类、批次、分数、位次、招生类型',
    'admissions.major_cutoffs': '专业或专业组录取数据，保留选科要求',
    'admissions.plans': '专业、计划数、学费、学制、选科要求及年份',
    'employment.outcomes': '毕业届次、统计口径与就业/升学指标',
    'community.snapshots': '可再分发上游数据子集的引用，保留未采用字段',
}
ENTRY_FIELDS = {
    'identity.external_identifiers': ['namespace','value'],
    'location.campuses': ['name','address','coordinates'],
    'visual.logo_assets': ['asset_id','kind','title','url','source','file_name','upstream_path','publisher','official',
        'repository','commit','repository_license','asset_license','rights_holder','format','width','height','vector',
        'representation','view_box','encoding','intrinsic_width','intrinsic_height','has_alpha','transparent_background','sha256','byte_size','access_status',
        'download_kind','archive_url','archive_member','archive_member_display','archive_sha256',
        'availability','verified','checked_at','usage_note','variant','dimensions_in_filename','source_type','identity_basis','resolved_url'],
    'visual.color_palette': ['value','rgb','cmyk','cmyk_text','pantone','label','role','method','official','current','basis','source',
        'verified','checked_at','availability','repository','commit','asset_id','source_sha256',
        'archive_member','archive_member_display','member_sha256'],
    'visual.vi_resources': ['title','url','kinds','formats','access_requirement','campus_district','source',
        'repository','commit','official','verified','checked_at','availability','note','publisher','use_scope',
        'edition_year','content_read','download_status','source_sha256','file_metadata','file_inspection','document_metadata'],
    'academics.subject_assessments': ['subject','grade','availability','candidates','round','assessment_year','publisher','completeness'],
    'rankings.entries': ['publisher','ranking_name','year','scope','rank','score','indicators','upstream_url'],
    'admissions.cutoffs': ['year','region','curriculum','batch','enrollment_type','minimum_score',
        'minimum_rank','major_group','score_difference','enrolled_count','reference_only'],
    'admissions.major_cutoffs': ['year','region','curriculum','batch','enrollment_type','major_name','major_code',
        'major_group','subject_requirements','minimum_score','minimum_rank','score_difference','reference_only'],
    'admissions.plans': ['year','region','curriculum','batch','enrollment_type','major_name','major_code',
        'planned_count','tuition','duration_years','subject_requirements','major_group'],
    'employment.outcomes': ['graduation_year','metric','value','unit','basis','population','data_as_of',
        'publisher','source_sha256','evidence'],
    'community.snapshots': ['repository','commit','data_path','school_code','upstream_record_name',
        'upstream_fields','source','license','data_as_of','verified','checked_at'],
}


def empty_fact():
    return dict(value=None, source=None, verified='unverified', checked_at=None,
                availability='unresearched', search_sources=[])


def official_name_variants(identity):
    """Use an alias only when already supported by this school's official site."""
    from research_all_schools import same_school
    names=[identity['name_zh']]
    home=identity.get('official_website',{}).get('value')
    alias=identity.get('short_name_zh',{})
    if (home and alias.get('availability')=='found' and alias.get('source_type')=='official_website'
            and alias.get('verified') in {'auto','human'} and isinstance(alias.get('value'),str)
            and len(alias['value'])>=2 and same_school(alias.get('source') or '',home)):
        names.append(alias['value'])
    return list(dict.fromkeys(names))


def migrate(profile):
    """Add typed fields while preserving all existing facts, lists and metadata."""
    if profile.get('schema_version') == 4:
        return profile
    for dotted in FACTS:
        group, key = dotted.split('.')
        profile.setdefault(group, {}).setdefault(key, empty_fact())
    for dotted in COLLECTIONS:
        group, key = dotted.split('.')
        profile.setdefault(group, {}).setdefault(key, [])
    profile['schema_version'] = SCHEMA_VERSION
    return profile


def rgb(hex_value):
    return [int(hex_value[i:i+2], 16) for i in (1, 3, 5)]


def upsert(items, entry, identity):
    """Stable keyed import: rerunning does not duplicate or erase human records."""
    key = identity(entry)
    for index, existing in enumerate(items):
        if identity(existing) == key:
            if existing.get('verified') != 'human':
                items[index] = copy.deepcopy(entry)
            return False
    items.append(copy.deepcopy(entry))
    return True


def put_fact(profile, dotted, value, metadata, **extra):
    if profile.get('schema_version') == 4:
        from ppt_scope import is_core_field
        if not is_core_field(dotted):
            raise ValueError('Field excluded by PPT core scope: ' + dotted)
    if value is None or value == '' or value == []:
        return False
    group, key = dotted.split('.')
    current = profile[group][key]
    # Existing authoritative or conflicting evidence is preserved.
    if current['availability'] != 'unresearched':
        if (current.get('verified') == 'auto' and current.get('value') == value
                and current.get('upstream_repository') == metadata.get('upstream_repository')
                and current.get('upstream_commit') == metadata.get('upstream_commit')):
            current.update(metadata, **extra)
        return False
    profile[group][key] = dict(value=copy.deepcopy(value), availability='found',
                              search_sources=[], **metadata, **extra)
    return True
