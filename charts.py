import re
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from calculation import summarize_rows


_FOLLOWUP = re.compile(
    r"(?:(?:그|이|방금|직전|앞선|계산한)\s*)?(?:결과(?:를|는|도)?\s*)?"
    r"(?:(월별)(?:로)?\s*)?(?:(막대|꺾은선|선)\s*)?(?:그래프|차트)"
    r"(?:(?:로|으로|를|을|도)\s*)?(?:(?:보여|그려|만들어)\s*(?:줘|주세요))?[.!?？]*"
)


def chart_request(text):
    match = _FOLLOWUP.fullmatch(text)
    if not match:
        return None
    monthly, shape = match.groups()
    if monthly and shape == "막대":
        raise ValueError("월별 비교는 '월별 꺾은선그래프로 보여줘'로 요청하세요.")
    return "monthly" if monthly or shape in ("꺾은선", "선") else "bar"


def monthly_points(result):
    columns = [i for i, col in enumerate(result.table.columns) if col.casefold() in ("월", "연월", "년월", "month", "year_month")]
    if len(columns) != 1:
        raise ValueError("월별 그래프에는 YYYY-MM 값을 가진 월 열 하나가 필요합니다 (예: 월, month).")
    groups = defaultdict(list)
    for n in result.rows:
        month = result.table.rows[n - 1][columns[0]].strip()
        if not re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", month):
            raise ValueError(f"자료 {n}행의 월을 YYYY-MM으로 확인할 수 없습니다.")
        groups[month].append(n)
    if len(groups) < 2:
        raise ValueError("월별 꺾은선에는 서로 다른 두 달 이상의 결과가 필요합니다.")
    return [(month, summarize_rows(result.table, result.request, groups[month])) for month in sorted(groups)]


def save_chart(result, kind, directory):
    from matplotlib import rc_context
    from matplotlib.figure import Figure
    from matplotlib.font_manager import get_font_names

    points = monthly_points(result) if kind == "monthly" else []
    fonts = set(get_font_names())
    families = [f for f in ("Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans CJK KR", "NanumGothic") if f in fonts]
    with rc_context({"font.family": families + ["DejaVu Sans"], "svg.fonttype": "none", "text.parse_math": False}):
        fig = Figure(figsize=(8, 4.4), layout="constrained")
        ax = fig.subplots()
        scope = ", ".join(f"{key}={', '.join(values)}" for key, values in result.request.filters.items()) or "전체"
        title = ("월별 " if points else "") + result.label
        fig.suptitle(title, fontweight="bold", fontsize=16)
        ax.set_title(f"{scope}  ·  일치 {len(result.rows)}건  ·  전체 결과 {result.measure.display}", fontsize=10, pad=14)
        ax.set_ylabel(result.measure.unit or result.label)
        ax.grid(axis="y", alpha=.23)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        if points:
            xs, ys, ticks, labels = [], [], [], []
            step = max(1, (len(points) + 6) // 7)
            for i, (month, measure) in enumerate(points):
                x = int(month[:4]) * 12 + int(month[5:])
                if xs and x != xs[-1] + 1:
                    xs.append(float("nan"))
                    ys.append(float("nan"))
                y = float(measure.amount)
                xs.append(x)
                ys.append(y)
                if i % step == 0 or i == len(points) - 1:
                    ticks.append(x)
                    labels.append(month)
                if len(points) <= 10:
                    ax.annotate(measure.display, (x, y), xytext=(0, 9), textcoords="offset points", ha="center")
            ax.plot(xs, ys, color="#146b61", marker="o" if len(points) <= 100 else ".", linewidth=2, gid="monthly-series")
            ax.set_xticks(ticks, labels, rotation=25 if len(labels) > 5 else 0)
            ax.margins(x=.12, y=.25)
        else:
            y = float(result.measure.amount)
            bars = ax.bar([0], [y], width=.46, color="#146b61")
            bars[0].set_gid("aggregate-bar")
            ax.set_xlim(-.8, .8)
            ax.set_xticks([0], ["계산 결과"])
            ax.annotate(result.measure.display, (0, y), xytext=(0, 7 if y >= 0 else -7),
                        textcoords="offset points", ha="center", va="bottom" if y >= 0 else "top")
            ax.margins(y=.2)
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=directory, prefix=kind + "-", suffix=".svg", delete=False) as out:
            path = Path(out.name)
            try:
                fig.savefig(out, format="svg")
            except Exception:
                out.close()
                path.unlink(missing_ok=True)
                raise
    return path.resolve()
