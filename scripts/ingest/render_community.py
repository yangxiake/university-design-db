#!/usr/bin/env python3
"""Generate a separate view of source-labelled community resources."""
import argparse
import pathlib
import yaml
ROOT = pathlib.Path(__file__).resolve().parents[2]

def render(profile):
    entries = profile['resources'].get('community_resources', [])
    if not entries:
        return None
    lines = ['# '+profile['identity']['name_zh']+'：社区资源', '',
             '由profile.yaml生成。社区作者整理，非学校官方发布；Beamer/Marp不等于PPTX。', '']
    for item in entries:
        lines += ['## '+item['title'], '',
                  '- 入口：['+item['url']+']('+item['url']+')',
                  '- 类型：`'+item['kind']+'`',
                  '- 发布者：'+item['publisher'],
                  '- 版本：`'+item['commit']+'`',
                  '- 许可：'+(item.get('license') or '未声明，仅提供入口'),
                  '- 依据：['+item['source']+']('+item['source']+')',
                  '- 采集：'+str(item['checked_at'])+'（'+item['verified']+'）',
                  '- 使用说明：'+item['usage_note']]
        for color in item.get('palette', []):
            lines += ['- 社区主题参考色：`'+color['value']+'`；'+color['basis']]
        lines += ['']
    return '\n'.join(lines)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true');args=parser.parse_args();count=0
    for path in sorted((ROOT/'universities').glob('*/*/profile.yaml')):
        expected=render(yaml.safe_load(path.read_text(encoding='utf-8')))
        output=path.with_name('COMMUNITY.md')
        if args.check:
            if expected is None and output.exists() or expected is not None and (not output.exists() or output.read_text(encoding='utf-8')!=expected):
                raise ValueError('Stale community view: '+str(output))
        elif expected is not None:
            output.write_text(expected,encoding='utf-8')
        elif output.exists():
            output.unlink()
        count+=expected is not None
    print(('Checked' if args.check else 'Generated')+' community views for '+str(count)+' schools.')
if __name__=='__main__':main()
