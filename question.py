import re


def requests_execution(text):
    active = re.sub(r'“[^”]*”|‘[^’]*’|"[^"]*"|\'[^\']*\'|`[^`]*`', ' ', text)
    ordinary = re.search(r'조회\s*해|계산\s*해|분석\s*해|분석.{0,5}(이어|진행|시작)|진행\s*해|몇\s*(명|건|원|개)|얼마|CSV.*(분석|입력|계산|이어)',active,re.I)
    metric = r'합계|합산|총합|총액|추이|추세|비중|구성비|점유율|순위|증감률?|(?:상위|하위)\s*(?:[0-9]+|한|두|세|네)\s*개'
    display = re.search(r'(?:' + metric + r')(?:(?!방법|산식|뜻|설명)[^.!?？\n]){0,80}'
                        r'보여\s*(?:줘|주세요)(?![가-힣])', active)
    comparison = re.search(r'비교\s*해\s*(?:줘|주세요)(?![가-힣])', active)
    return bool(ordinary or display or comparison)


def download_page_question(text):
    if requests_execution(text) or not re.search(
            r'어떤\s*(?:파일|자료)|무슨\s*(?:파일|자료)|뭘\s*(?:받|선택)'
            r'|어디(?:서|에서).{0,20}(?:받|다운)|다운로드\s*(?:방법|어떻게)', text):
        return None
    links = tuple(dict.fromkeys(url.rstrip('.,!?？。)') for url in re.findall(r'https?://[^\s<>"“”]+', text)))
    return links[0] if len(links) == 1 else None
