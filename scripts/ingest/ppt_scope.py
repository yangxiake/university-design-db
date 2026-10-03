"""One field allowlist for canonical PPT facts, collectors and gap reports."""
import copy
import pathlib

from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCOPE = load_yaml((ROOT / 'data/ppt-core-fields.yaml').read_text(encoding='utf-8'))
FACT_FIELDS = {key: label for section in ('required_facts', 'support_facts', 'optional_facts')
               for key, label in SCOPE[section].items()}
LIST_FIELDS = dict(SCOPE['required_collections'], **SCOPE['optional_collections'])
REQUIRED = set(SCOPE['required_facts']) | set(SCOPE['required_collections'])


def is_core_field(dotted):
    return dotted in FACT_FIELDS or dotted in LIST_FIELDS


def core_profile(profile):
    """Project onto the approved scope; never carry unwanted statistics in text."""
    result = {key: copy.deepcopy(profile[key]) for key in ('classification', 'research')}
    result['schema_version'] = SCOPE['schema_version']
    result['identity'] = {key: copy.deepcopy(profile['identity'][key]) for key in SCOPE['identity_keys']}
    for dotted in FACT_FIELDS:
        group, key = dotted.split('.')
        result.setdefault(group, {})[key] = copy.deepcopy(profile[group][key])
    for dotted in LIST_FIELDS:
        group, key = dotted.split('.')
        result.setdefault(group, {})[key] = copy.deepcopy(profile[group].get(key, []))
    # The brief is inexpensive to maintain because its only input is registry
    # identity. A copied old overview could retain removed counts or rankings.
    identity = result['identity']
    result['overview']['summary_zh'] = dict(
        value='%s位于%s%s，教育部名单列为%s，主管部门为%s。' % (
            identity['name_zh'], identity['province'], identity['city'], identity['level'], identity['authority']),
        source=identity['registry_source'], verified='auto', checked_at=SCOPE['effective_date'],
        availability='found', search_sources=[], source_type='official_registry',
        basis='仅由教育部身份主字段生成；不含招生、就业、排名、人数或面积。',
        collector='ppt_core_identity_summary')
    return {key: result[key] for key in ('schema_version', 'identity', 'classification', 'research', 'visual', 'culture', 'resources', 'overview')}
