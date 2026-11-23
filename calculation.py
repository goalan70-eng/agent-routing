import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path

from decision import AnalysisRequest


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def read_table(path):
    limit = 2 * 1024 * 1024
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("2 MiB 이하의 CSV를 선택하세요.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp949")
    if "\x00" in text:
        raise ValueError("쉼표로 구분한 CSV가 필요합니다.")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    columns = tuple(s.strip() for s in next(reader, []))
    if not columns or not all(columns) or len(set(columns)) != len(columns):
        raise ValueError("첫 행의 열 이름이 비었거나 중복됩니다.")
    if len(columns) > 128:
        raise ValueError("최대 128열까지 지원합니다.")
    rows = []
    for record in reader:
        if len(rows) >= 50000:
            raise ValueError("최대 50,000개 자료 행까지 지원합니다.")
        if len(record) != len(columns):
            raise ValueError(f"자료 {len(rows) + 1}행의 열 개수가 다릅니다.")
        rows.append(tuple(record))
    return Table(columns, tuple(rows))


operations = {"건수": "count", "몇 건": "count", "합계": "sum", "평균": "mean"}


def parse_request(question, table):
    text = re.sub(r"^(?:이\s*파일에서|이\s*CSV에서)\s*", "", question.strip(), flags=re.I)
    text = re.sub(r"\s*[.?!？]+\s*$", "", text)
    text = re.sub(r"\s*(?:구해|계산해|알려|보여)\s*(?:줘|주세요)$", "", text)
    text = re.sub(r"(?:을|를|이야|인가요)$", "", text.strip()).strip()
    match = re.fullmatch(rf"(?:(?P<scope>.+?)의\s+)?(?P<body>.+)", text)
    if not match:
        raise ValueError("예: A지점의 평균 관측값을 구해줘")
    body = match["body"]
    # Match a registered column verbatim, on either side of the operation.
    pairs = [(op, col) for op in operations for col in table.columns
             if body in (f"{op} {col}", f"{col} {op}")]
    if body in ("건수", "몇 건", "몇건"):
        operation, metric = "count", ""
    elif len(pairs) == 1:
        op, metric = pairs[0]
        operation = operations[op]
    else:
        raise ValueError("열 이름과 건수·합계·평균 중 하나를 지정하세요. 현재 열: " + ", ".join(table.columns))
    filters = {}
    scope = match["scope"]
    if scope and scope != "전체":
        scope = scope.strip()
        if "=" in scope:
            column, value = (s.strip() for s in scope.split("=", 1))
            if column not in table.columns or not value:
                raise ValueError("조건은 열이름=값 형식으로 입력하세요.")
        else:
            candidates = [c for i, c in enumerate(table.columns) if any(row[i].strip() == scope for row in table.rows)]
            if len(candidates) != 1:
                raise ValueError("조건의 열을 특정할 수 없습니다. 열이름=값으로 지정하세요.")
            column, value = candidates[0], scope
        filters[column] = (value,)
    return AnalysisRequest(operation=operation, metric=metric, filters=filters, group_by=())


def calculate(table, request):
    if request.operation not in ("count", "sum", "mean"):
        raise ValueError("지원하는 연산은 건수·합계·평균입니다.")
    filters = [(table.columns.index(c), values) for c, values in request.filters.items()]
    selected = [(n, row) for n, row in enumerate(table.rows, 1)
                if all(row[i].strip() in values for i, values in filters)]
    ids = [n for n, _ in selected]
    if request.operation == "count":
        return str(len(ids)), ids
    if not selected:
        raise ValueError("조건과 일치하는 자료 행이 없습니다.")
    index = table.columns.index(request.metric)
    unit_cols = [i for i, c in enumerate(table.columns)
                 if c.casefold() in {"단위", "unit", request.metric.casefold() + "_unit", request.metric + "단위"}]
    units = {row[i].strip() for _, row in selected for i in unit_cols}
    if "" in units or len(units) > 1:
        raise ValueError("선택한 행의 단위가 비었거나 서로 다릅니다.")
    with localcontext() as ctx:
        ctx.prec = 64
        total = Decimal(0)
        for n, row in selected:
            raw = row[index].strip()
            if len(raw) > 26 or not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", raw):
                raise ValueError(f"자료 {n}행의 {request.metric} 값이 비었거나 숫자가 아닙니다.")
            total += Decimal(raw.replace(",", ""))
        result = total if request.operation == "sum" else total / len(selected)
        value = format(result.normalize(), "f")
        if request.operation == "mean" and result.as_tuple().exponent < -6:
            rounded = result.quantize(Decimal("0.000001"))
            if rounded != result:
                value = "약 " + format(rounded, "f")
    return value + (" " + next(iter(units)) if units else ""), ids
