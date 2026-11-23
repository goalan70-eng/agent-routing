import argparse
import csv
import re
from pathlib import Path

from calculation import calculate, parse_request, read_table
from catalog import load_sources, recommend
from decision import ChatDecision
from question import requests_execution


CATALOG = Path(__file__).with_name("sources.json")


class Session:
    def __init__(self, sources):
        self.sources = sources
        self.table = None

    def attach(self, path):
        self.table = None
        self.table = read_table(path)
        return f"선택한 로컬 CSV: {Path(path).name} · {len(self.table.rows)}행 · " + ", ".join(self.table.columns)

    def respond(self, question):
        text = question.strip()
        if not text:
            raise ValueError("질문을 입력하세요.")
        if text.startswith("파일 "):
            return self.attach(text[3:].strip().strip('"'))
        search = re.match(r"^검색\s+(.+)$", text)
        lookup = re.search(r"(?:자료|데이터|원본|파일).*(?:어디|찾|받|링크|추천)|(?:다운로드|제공처|공식\s*링크)", text)
        metric = re.search(r"평균|합계|건수|몇\s*건", text)
        execute = requests_execution(text)
        if not search and lookup and execute and re.search(r"계산\s*해|분석\s*해", text):
            raise ValueError("자료 검색과 파일 계산을 차례로 요청하세요.")
        file_task = metric or (execute and (self.table is not None or re.search(r"계산|분석", text)))
        if not search and not lookup and file_task:
            if self.table is None:
                raise ValueError("먼저 '파일 경로.csv'로 계산할 CSV를 선택하세요.")
            decision = ChatDecision(action="analyze", analysis=parse_request(text, self.table))
        else:
            decision = ChatDecision(action="search", query=search[1] if search else text)

        if decision.action == "search":
            hits = recommend(decision.query, self.sources)
            if not hits:
                return "등록한 공식 자료 중 일치하는 항목이 없습니다."
            return "\n\n".join(
                f"{source['agency']} · {source['title']}\n{source['description']}\n"
                f"{source['url']}\n일치한 검색어: {', '.join(matches)}"
                for source, matches in hits
            )
        value, rows = calculate(self.table, decision.analysis)
        operation = {"count": "건수", "mean": "평균", "sum": "합계"}[decision.analysis.operation]
        label = " ".join(filter(None, [decision.analysis.metric, operation]))
        shown = ", ".join(str(n) for n in rows[:20]) or "없음"
        if len(rows) > 20:
            shown += f" 외 {len(rows) - 20}행"
        return f"{label}: {value}\n일치 {len(rows)}건 · 자료 행(헤더 제외): {shown}"


def main():
    parser = argparse.ArgumentParser(description="공식 자료 추천 및 로컬 CSV 계산")
    parser.add_argument("question", nargs="?", help="생략하면 대화 모드")
    parser.add_argument("--csv", type=Path, help="로컬 CSV 경로")
    parser.add_argument("--catalog", type=Path, default=CATALOG, help="공식 출처 등록 목록")
    args = parser.parse_args()
    errors = (OSError, ValueError, csv.Error)
    try:
        session = Session(load_sources(args.catalog))
        if args.csv:
            print(session.attach(args.csv))
        if args.question is not None:
            print(session.respond(args.question))
            return 0
    except errors as exc:
        parser.exit(1, f"{exc}\n")
    print("자료를 질문하거나 '파일 경로.csv'로 로컬 CSV를 여세요. 마치려면 '종료'.")
    while True:
        try:
            question = input("> ")
        except EOFError:
            return 0
        if question.strip() == "종료":
            return 0
        try:
            print(session.respond(question))
        except errors as exc:
            print(exc)


if __name__ == "__main__":
    raise SystemExit(main())
