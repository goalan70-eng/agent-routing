import argparse
import csv
import re
import sys
import webbrowser
from pathlib import Path

from calculation import calculate_result, parse_request, read_table
from catalog import load_sources, recommend
from charts import chart_request, save_chart
from decision import ChatDecision
from question import requests_execution


CATALOG = Path(__file__).with_name("sources.json")


class Session:
    def __init__(self, sources, chart_dir="charts", *, open_charts=False):
        self.sources = sources
        self.table = None
        self.last_result = None
        self.chart_dir = chart_dir
        self.open_charts = open_charts

    def attach(self, path):
        self.last_result = None
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
        if not search and (kind := chart_request(text)):
            if self.last_result is None:
                raise ValueError("그래프로 표시할 계산 결과가 없습니다. 먼저 CSV에서 건수·합계·평균을 계산하세요.")
            path = save_chart(self.last_result, kind, self.chart_dir)
            if self.open_charts:
                webbrowser.open(path.as_uri())
            return f"그래프: {path.as_uri()}"
        self.last_result = None
        if not search and re.search(r"그래프|차트", text) and re.search(r"보여|그려|만들어", text):
            raise ValueError("조건을 지정해 먼저 계산한 뒤 '그 결과를 그래프로 보여줘'라고 요청하세요.")
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
        result = calculate_result(self.table, decision.analysis)
        self.last_result = result
        rows = result.rows
        shown = ", ".join(str(n) for n in rows[:20]) or "없음"
        if len(rows) > 20:
            shown += f" 외 {len(rows) - 20}행"
        return f"{result.label}: {result.measure.display}\n일치 {len(rows)}건 · 자료 행(헤더 제외): {shown}"


def main():
    parser = argparse.ArgumentParser(description="공식 자료 추천 및 로컬 CSV 계산")
    parser.add_argument("question", nargs="?", help="생략하면 대화 모드")
    parser.add_argument("--csv", type=Path, help="로컬 CSV 경로")
    parser.add_argument("--catalog", type=Path, default=CATALOG, help="공식 출처 등록 목록")
    parser.add_argument("--chart-dir", type=Path, default=Path("charts"), help="SVG 그래프 저장 폴더")
    args = parser.parse_args()
    errors = (OSError, ValueError, csv.Error)
    try:
        session = Session(load_sources(args.catalog), args.chart_dir, open_charts=sys.stdin.isatty())
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
