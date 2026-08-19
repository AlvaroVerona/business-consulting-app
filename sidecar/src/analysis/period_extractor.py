"""Turns a project's ingested CSV/XLSX rows into structured financial
periods, by matching common column-name aliases — no LLM. If the column
names don't match anything recognized, the row is silently skipped rather
than guessed at; a wrong guess here would corrupt every metric downstream."""

import re

from src.analysis.financial import PeriodMetrics, cost_ratio, ebitda_margin, gross_margin, implied_ebitda
from src.database.models import DocumentChunk

_ALIASES: dict[str, set[str]] = {
    "period": {"period", "month", "mes", "fecha", "date", "quarter", "trimestre"},
    "revenue": {"revenue", "sales", "ingresos", "ventas", "facturacion"},
    "cogs": {"cogs", "cost_of_goods_sold", "cost of goods sold", "costo_de_ventas", "costo de ventas"},
    "opex": {"opex", "sga", "sg&a", "operating_expenses", "operating expenses", "gastos_operativos", "gastos operativos"},
    "ebitda": {"ebitda"},
}


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9&]+", "_", key.strip().lower()).strip("_")


def _match_field(key: str) -> str | None:
    normalized = _normalize_key(key)
    for field, aliases in _ALIASES.items():
        if normalized in {_normalize_key(a) for a in aliases}:
            return field
    return None


def _parse_row(content: str) -> dict[str, str]:
    """Reverses CSVParser/XLSXParser's `"col: val; col: val"` chunk format."""

    fields: dict[str, str] = {}

    for part in content.split("; "):
        if ": " not in part:
            continue
        key, _, value = part.partition(": ")
        fields[key.strip()] = value.strip()

    return fields


def _to_float(raw: str) -> float | None:
    cleaned = raw.replace(",", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_periods(chunks: list[DocumentChunk]) -> list[PeriodMetrics]:
    periods: list[PeriodMetrics] = []

    for chunk in chunks:
        fields = _parse_row(chunk.content)
        matched: dict[str, float | str] = {}

        for key, raw_value in fields.items():
            field = _match_field(key)
            if field is None:
                continue

            if field == "period":
                matched["period"] = raw_value
            else:
                value = _to_float(raw_value)
                if value is not None:
                    matched[field] = value

        revenue = matched.get("revenue")
        cogs = matched.get("cogs")
        opex = matched.get("opex")
        ebitda = matched.get("ebitda")

        # Minimum bar to be useful: a labeled period plus revenue and cogs.
        if "period" not in matched or revenue is None or cogs is None:
            continue

        ebitda_is_implied = False
        if ebitda is None and opex is not None:
            ebitda = implied_ebitda(revenue, cogs, opex)
            ebitda_is_implied = True

        periods.append(
            PeriodMetrics(
                period=str(matched["period"]),
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                revenue=revenue,
                cogs=cogs,
                opex=opex,
                ebitda=ebitda,
                ebitda_is_implied=ebitda_is_implied,
                gross_margin=gross_margin(revenue, cogs) if revenue else None,
                ebitda_margin=ebitda_margin(revenue, ebitda) if (revenue and ebitda is not None) else None,
                opex_ratio=cost_ratio(opex, revenue) if (revenue and opex is not None) else None,
            )
        )

    return periods
