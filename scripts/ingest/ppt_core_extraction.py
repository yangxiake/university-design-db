"""Read founding-year wording with explicit current-school or predecessor scope."""
import datetime as dt
import re


def additional_claims(name, kind, title, text, source):
    if kind not in {'overview', 'charter', 'history'} or not re.search(r'简介|概况|章程|沿革|历史|概览|走进', title):
        return []
    out = []; own = re.escape(name)
    for raw in re.split(r'[\n。！？]', text):
        sentence = re.sub(r'\s+', '', raw)
        sentence = re.sub(r'^【(?:历史沿革|学校历史|办学历史)】', '', sentence)
        subject = re.match(r'^(?:第[一二三四五六七八九十百0-9]+条)?(?:' + own + r'|学校|本校)', sentence)
        if not subject or len(sentence) > 5000:
            continue
        rest = sentence[subject.end():]
        # School-name parentheticals can contain the former full name.
        rest = re.sub(r'^[（(][^）)]{0,100}[）)]', '', rest).lstrip('，,')
        origin = re.search(r'(?:办学(?:历史)?(?:源于|起源于|始于)|肇始于|(?:的|其)?前身(?:是|为|可追溯[至到]|可以追溯[至到]|追溯[至到]))([^。；]{0,180})', rest[:240])
        if origin:
            match = re.search(r'(\d{4})年', origin[1])
            if match and re.search(r'创办|创建|筹办|成立|始建|组建|设立|讲习所|师范学校|技训班', origin[1]):
                year = int(match[1])
                if 1000 <= year <= dt.date.today().year:
                    out.append(dict(field='culture.founded_year', value=year, source=source,
                        basis='官网明确记载本校办学来源或前身起点；该年不等同现名设立年。', evidence=origin[0][:150]))
            continue
        direct = re.search(r'(?:始建|创建|创办|创立|建校|成立)(?:于)?(\d{4})年|(\d{4})年(?:\d{1,2}月)?(?:(?:经|国家|由)[^，；]{0,45}?(?:批准|出资))?(?:正式)?(?:创办|创立|创建|成立)', rest[:220])
        if direct:
            before = rest[:direct.start()]
            if re.search(r'前身|分校|研究院|实验室|附属|项目|中心|校区|[一二]级学院|产业学院|联合学院|合作大学|合并', before):
                continue
            year = int(direct[1] or direct[2])
            if 1000 <= year <= dt.date.today().year:
                out.append(dict(field='culture.founded_year', value=year, source=source,
                    basis='官网以本校为主语明确记载创办/成立时间；不把筹建、更名或新校区年份代填。', evidence=sentence[:150]))
    return out
