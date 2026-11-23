import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from agent import Session
from calculation import Table
from charts import monthly_points

ROOT = Path(__file__).resolve().parent
NS = {"svg": "http://www.w3.org/2000/svg"}


def read_chart(path):
    root = ET.parse(path)
    labels = [node.text for node in root.findall(".//svg:text", NS)]
    return root, labels


class ChartTests(unittest.TestCase):
    def test_cli_both_charts_use_only_the_three_matching_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            turns = ["파일 examples/synthetic.csv", "A지점의 평균 관측값을 구해줘",
                     "그 결과를 그래프로 보여줘", "그 결과를 월별 꺾은선그래프로 보여줘", "종료"]
            run = subprocess.run([sys.executable, "agent.py", "--chart-dir", directory], cwd=ROOT,
                                 input="\n".join(turns), encoding="utf-8", capture_output=True,
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8"), check=True, timeout=90)
            self.assertIn("자료 행(헤더 제외): 1, 3, 4", run.stdout)
            self.assertEqual(run.stdout.count("그래프: file:"), 2, run.stdout)
            (bar_file,) = path.glob("bar-*.svg")
            (line_file,) = path.glob("monthly-*.svg")
            bar, labels = read_chart(bar_file)
            self.assertIsNotNone(bar.find(".//*[@id='aggregate-bar']/svg:path", NS))
            self.assertIn("12 ppm", labels)
            line, labels = read_chart(line_file)
            self.assertIn("지점=A지점  ·  일치 3건  ·  전체 결과 12 ppm", labels)
            for text in ["2025-01", "2025-02", "2025-03", "10 ppm", "12 ppm", "14 ppm"]:
                self.assertIn(text, labels)
            self.assertNotIn("70 ppm", labels)
            self.assertEqual(len(line.findall(".//*[@id='monthly-series']//svg:use", NS)), 3)

    def test_months_reuse_operation_sort_and_break_at_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session([], directory)
            session.table = Table(("월", "값"), (("2025-03", "-1"), ("2025-01", "10"), ("2025-01", "6")))
            for query, expected in [("값 평균", [8, -1]), ("값 합계", [16, -1]), ("건수", [2, 1])]:
                session.respond(query)
                points = monthly_points(session.last_result)
                self.assertEqual([(m, v.amount) for m, v in points], list(zip(["2025-01", "2025-03"], expected)))
            session.respond("월별 꺾은선그래프로 보여줘")
            (svg,) = Path(directory).glob("*.svg")
            line, _ = read_chart(svg)
            path = line.find(".//*[@id='monthly-series']/svg:path", NS).get("d")
            self.assertEqual(path.count("M"), 2)
            self.assertNotIn("L", path)

    def test_no_stale_result_after_failed_query_search_or_new_file(self):
        session = Session([])
        path = ROOT / "examples/synthetic.csv"
        for change in ["검색 관측", "없는열 평균", "파일 " + str(path)]:
            session.attach(path)
            session.respond("A지점의 건수")
            if change == "없는열 평균":
                with self.assertRaises(ValueError):
                    session.respond(change)
            else:
                session.respond(change)
            with self.assertRaisesRegex(ValueError, "먼저"):
                session.respond("그 결과를 그래프로 보여줘")

    def test_monthly_requires_supported_months_in_selected_rows(self):
        session = Session([])
        for columns, rows in [(("날짜",), (("2025-01",),)), (("월",), (("미상",),)), (("월",), (("2025-01",),))]:
            session.table = Table(columns, rows)
            session.respond("건수")
            with self.assertRaises(ValueError):
                session.respond("월별 꺾은선그래프로 보여줘")

    def test_new_calculation_supersedes_previous_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session([], directory)
            session.attach(ROOT / "examples/synthetic.csv")
            session.respond("A지점의 평균 관측값을 구해줘")
            session.respond("B지점의 관측값 합계")
            session.respond("그 결과를 막대그래프로 보여줘")
            (svg,) = Path(directory).glob("*.svg")
            _, labels = read_chart(svg)
            self.assertIn("관측값 합계", labels)
            self.assertIn("지점=B지점  ·  일치 1건  ·  전체 결과 70 ppm", labels)
