import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from agent import CATALOG, Session
from calculation import Table
from catalog import load_sources
from decision import ChatDecision
from interpret import PublicInterpreter


ROOT = Path(__file__).resolve().parent


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.session = Session(load_sources(CATALOG))

    def test_public_interpretation_for_an_arbitrary_subject(self):
        provider = Mock()
        provider.complete.return_value = SimpleNamespace(content=json.dumps({
            "action": "consult", "intent": {"topic": "air_quality", "data_source": "station_csv"}
        }), prompt_tokens=3, completion_tokens=2)
        events = []
        interpreter = PublicInterpreter()
        plan = interpreter._interpret_public(provider, [], lambda kind, label: events.append((kind, label)), None)
        self.assertEqual((plan.action, plan.intent.topic, plan.intent.data_source), ("consult", "air_quality", "local_csv"))
        self.assertEqual(events[0], ("OPENAI_RUNNING", "공개 자료에 대한 질문을 해석하고 있습니다."))
        self.assertEqual(interpreter.usage, {"calls": 1, "prompt_tokens": 3, "completion_tokens": 2})

    def test_consult_still_validates_tool_inputs(self):
        for source in ("local_csv", "auto", None):
            self.assertEqual(ChatDecision(action="consult", intent={"data_source": source}).intent.data_source, source)
        for invalid in ({"topic": ""}, {"topic": "two words"}, {"data_source": "https://example.invalid/a_csv"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                ChatDecision(action="consult", intent=invalid)

    def test_cli_from_source_search_to_local_evidence(self):
        turns = [
            "월평균 이산화탄소 자료는 어디서 받아?", "최근 지진을 찾고 싶어",
            "파일 examples/synthetic.csv", "이 파일에서 A지점의 평균 관측값을 구해줘",
            "지점=A지점의 관측값 합계를 알려줘", "A지점의 건수", "종료",
        ]
        run = subprocess.run([sys.executable, "agent.py"], cwd=ROOT, input="\n".join(turns) + "\n",
                             capture_output=True, encoding="utf-8", check=True,
                             env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=15)
        for expected in ("https://gml.noaa.gov/ccgg/trends/data.html", "일치한 검색어: 이산화탄소",
                         "https://earthquake.usgs.gov/earthquakes/search/", "synthetic.csv · 4행",
                         "관측값 평균: 12 ppm", "관측값 합계: 36 ppm", "건수: 3"):
            self.assertIn(expected, run.stdout)
        self.assertEqual(run.stdout.count("일치 3건 · 자료 행(헤더 제외): 1, 3, 4"), 3)

    def test_unregistered_source(self):
        self.assertNotIn("https://", self.session.respond("도서관 자료를 추천해줘"))

    def test_new_subject_with_only_catalog_changed(self):
        entry = dict(agency="테스트 기관", title="가상 강좌", url="https://example.invalid/classes",
                     description="가상 목록", keywords=["강좌"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "list.json"
            path.write_text(json.dumps([entry]), encoding="utf-8")
            alternate = Session(load_sources(path))
            self.assertIn(entry["url"], alternate.respond("강좌를 찾고 싶어"))
            self.assertNotIn("https://", alternate.respond("강좌비 자료"))
            entry["url"] = "http://example.invalid/classes"
            path.write_text(json.dumps([entry]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_sources(path)

    def test_failed_attachment_clears_prior_data(self):
        self.session.attach(ROOT / "examples/synthetic.csv")
        with self.assertRaises(FileNotFoundError):
            self.session.attach(ROOT / "missing.csv")
        with self.assertRaisesRegex(ValueError, "먼저"):
            self.session.respond("전체의 관측값 평균")

    def test_invalid_values_are_not_silently_omitted(self):
        for value in ["", "자료 없음", "NaN", "12,34"]:
            with self.subTest(value=value):
                self.session.table = Table(("값",), (("3",), (value,)))
                with self.assertRaisesRegex(ValueError, "2행"):
                    self.session.respond("값 평균")

    def test_mixed_units_and_ambiguous_filter(self):
        self.session.table = Table(("대상", "분류", "값", "단위"),
                                   (("A", "A", "1", "원"), ("A", "B", "1", "천원")))
        with self.assertRaisesRegex(ValueError, "열을 특정"):
            self.session.respond("A의 건수")
        with self.assertRaisesRegex(ValueError, "단위"):
            self.session.respond("대상=A의 값 합계")
        self.assertIn("건수: 0", self.session.respond("대상=X의 건수"))
        with self.assertRaisesRegex(ValueError, "일치"):
            self.session.respond("대상=X의 값 평균")

    def test_decimal_arithmetic_and_filter_scope(self):
        self.session.table = Table(("구분", "값"), (("A", "0.1"), ("B", "0.2")))
        self.assertIn("값 합계: 0.3", self.session.respond("전체의 값 합계"))
        self.assertIn("값 평균: 0.15", self.session.respond("값 평균"))
        with self.assertRaises(ValueError):
            self.session.respond("2020년만 값 합계")

    def test_mixed_search_and_calculation(self):
        with self.assertRaisesRegex(ValueError, "차례"):
            self.session.respond("지진 자료를 찾고 평균을 계산해줘")


if __name__ == "__main__":
    unittest.main()
