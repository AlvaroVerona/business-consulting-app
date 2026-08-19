from src.analysis.period_extractor import extract_periods
from src.database.models import DocumentChunk


def _chunk(id: int, document_id: int, content: str) -> DocumentChunk:
    chunk = DocumentChunk(document_id=document_id, order_index=0, content=content, location={"row": id})
    chunk.id = id
    return chunk


def test_extracts_period_with_revenue_and_cogs():
    chunks = [_chunk(1, 10, "month: Jan; revenue: 1000; cogs: 600")]

    periods = extract_periods(chunks)

    assert len(periods) == 1
    p = periods[0]
    assert p.period == "Jan"
    assert p.revenue == 1000
    assert p.cogs == 600
    assert p.gross_margin == 0.4
    assert p.chunk_id == 1
    assert p.document_id == 10


def test_infers_ebitda_when_opex_present_but_ebitda_absent():
    chunks = [_chunk(1, 10, "month: Jan; revenue: 1000; cogs: 600; opex: 200")]

    p = extract_periods(chunks)[0]

    assert p.ebitda == 200
    assert p.ebitda_is_implied is True
    assert p.ebitda_margin == 0.2


def test_uses_reported_ebitda_when_present():
    chunks = [_chunk(1, 10, "month: Jan; revenue: 1000; cogs: 600; ebitda: 250")]

    p = extract_periods(chunks)[0]

    assert p.ebitda == 250
    assert p.ebitda_is_implied is False


def test_recognizes_spanish_column_aliases():
    chunks = [_chunk(1, 10, "mes: Enero; ingresos: 1000; costo de ventas: 600")]

    p = extract_periods(chunks)[0]

    assert p.period == "Enero"
    assert p.revenue == 1000
    assert p.cogs == 600


def test_skips_rows_missing_required_fields():
    chunks = [
        _chunk(1, 10, "item: some unrelated inventory row; qty: 5"),
        _chunk(2, 10, "month: Jan; revenue: 1000"),  # no cogs
    ]

    assert extract_periods(chunks) == []


def test_tolerates_currency_formatting():
    chunks = [_chunk(1, 10, "month: Jan; revenue: $1,000; cogs: $600")]

    p = extract_periods(chunks)[0]

    assert p.revenue == 1000
    assert p.cogs == 600
