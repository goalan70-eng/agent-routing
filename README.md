# Agent routing

- `question.py` — 다운로드 안내 요청과 계산 요청을 구분합니다.
- `interpret.py` — 공개 질문에 대한 모델 응답을 읽어 다음 행동으로 변환합니다.
- `decision.py` — 제안된 행동과 그에 필요한 입력을 검증합니다.

`reply`면 직접 답하고, `consult`면 분석 담당 도구를 선택합니다. 일반 도구 호출은 컨트롤러에서 다음과 같이 넘깁니다.

```python
outcome = self.tools.execute(decision, text, allow_remote=not no_query)
```

## 공식 자료 검색과 CSV 계산

Python 3.12에서 아래 명령으로 대화를 시작합니다. API 키 없이 실행할 수 있습니다.

```sh
python -m pip install -r requirements.txt
python agent.py
```

```text
> 월별 이산화탄소 자료는 어디서 받아?
> 파일 examples/synthetic.csv
> A지점의 평균 관측값을 구해줘
관측값 평균: 12 ppm
일치 3건 · 자료 행(헤더 제외): 1, 3, 4
> 그 결과를 그래프로 보여줘
> 그 결과를 월별 꺾은선그래프로 보여줘
```

검색 결과에는 공식 페이지와 일치한 검색어가 표시됩니다. 기본 출처는 [NOAA 대기 관측 자료](https://gml.noaa.gov/ccgg/trends/data.html)와 [USGS 지진 목록](https://earthquake.usgs.gov/earthquakes/search/)입니다. 다른 분야는 `sources.json` 형식으로 기관·자료명·공식 주소·설명·검색어를 등록한 뒤 `--catalog 목록.json`으로 사용할 수 있습니다.

계산은 직접 선택한 로컬 CSV에 적용합니다. 예시 파일의 수치는 모두 가상입니다. `A지점의 건수`, `지점=A지점의 관측값 합계`, `전체의 관측값 평균`을 지원합니다. 단위가 있는 자료는 `단위` 또는 `unit` 열에 표시하세요. 자료 행 번호는 헤더 다음부터 1로 셉니다.

대화 중 “그 결과를 그래프로 보여줘”라고 하면 직전 계산값을 막대로 표시합니다. “월별 꺾은선그래프로 보여줘”는 같은 행·열·연산을 월별로 묶어 표시합니다. 위 예시에서는 막대가 12 ppm이고, 꺾은선은 1월 10, 2월 12, 3월 14 ppm입니다. 관측이 빠진 달에서는 선이 끊깁니다.

그래프는 `charts/`에 SVG로 저장되며 대화형 터미널에서는 브라우저로 열립니다. 저장 위치는 `--chart-dir`으로 변경할 수 있습니다.
