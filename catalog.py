import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit


def words(text):
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold())


def load_sources(path):
    entries = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(entries, list):
        raise ValueError("출처 목록은 JSON 배열이어야 합니다.")
    for entry in entries:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(key), str) and entry[key].strip()
            for key in ("title", "agency", "url", "description")
        ):
            raise ValueError("출처의 제목·기관·주소·설명이 필요합니다.")
        url = urlsplit(entry["url"])
        if url.scheme != "https" or not url.hostname or url.username is not None or url.password is not None:
            raise ValueError("출처에는 인증정보가 없는 HTTPS 주소를 등록하세요.")
        keywords = entry.get("keywords")
        if not isinstance(keywords, list) or not keywords or not all(isinstance(k, str) and words(k) for k in keywords):
            raise ValueError("각 출처에 검색어를 하나 이상 등록하세요.")
    return entries


def recommend(query, entries):
    tokens = words(query)
    # Match complete words or a word with a common Korean particle.
    particles = {"", "을", "를", "이", "가", "에", "의", "은", "는", "와", "과", "도", "에서", "으로", "로"}
    results = []
    for entry in entries:
        matches = []
        for keyword in dict.fromkeys(entry["keywords"]):
            term = words(keyword)
            for i in range(len(tokens) - len(term) + 1):
                window = tokens[i:i + len(term)]
                if (window[:-1] == term[:-1] and window[-1].startswith(term[-1])
                        and window[-1][len(term[-1]):] in particles):
                    matches.append(keyword)
                    break
        if matches:
            results.append((entry, matches))
    return sorted(results, key=lambda hit: -len(hit[1]))
