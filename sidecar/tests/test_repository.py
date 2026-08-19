from src.database.repository import Repository


def test_company_project_document_finding_roundtrip(db_session):
    repo = Repository(db_session)

    company = repo.create_company(name="Acme Wine Bar", industry="hospitality")
    assert company.id is not None

    project = repo.create_project(company.id, name="2026 diagnostic", description="EBITDA decline")
    assert project.company_id == company.id

    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(document.id, [{"content": "revenue: 1000", "location": {"row": 2}}])
    repo.set_document_status(document.id, "INDEXED")

    refreshed = repo.get_document(document.id)
    assert refreshed.status == "INDEXED"

    chunks = repo.list_chunks(project.id)
    assert len(chunks) == 1
    assert chunks[0].content == "revenue: 1000"

    finding = repo.create_finding(
        project_id=project.id,
        statement="Revenue was 1000 in the period shown.",
        source_type="FACT",
        confidence="HIGH",
        document_id=document.id,
        chunk_id=chunks[0].id,
        location={"row": 2},
    )
    assert finding.id is not None
    assert repo.list_findings(project.id)[0].statement.startswith("Revenue was")

    repo.add_chat_message(project.id, role="user", content="Why did EBITDA decline?")
    repo.add_chat_message(project.id, role="assistant", content="...", finding_ids=[finding.id])
    messages = repo.list_chat_messages(project.id)
    assert [m.role for m in messages] == ["user", "assistant"]


def test_list_chunks_orders_by_document_upload_time_then_position(db_session):
    """Regression: list_chunks had no ORDER BY, so with two documents in a
    project, chunk order (and therefore extract_periods' "first"/"last"
    period) depended on unspecified SQL result order."""
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    doc_a = repo.create_document(project.id, filename="a.csv", file_type="csv", storage_path="/tmp/a.csv")
    repo.add_chunks(doc_a.id, [{"content": "a-row-0"}, {"content": "a-row-1"}])

    doc_b = repo.create_document(project.id, filename="b.csv", file_type="csv", storage_path="/tmp/b.csv")
    repo.add_chunks(doc_b.id, [{"content": "b-row-0"}, {"content": "b-row-1"}])

    contents = [c.content for c in repo.list_chunks(project.id)]

    assert contents == ["a-row-0", "a-row-1", "b-row-0", "b-row-1"]


def test_list_projects_scoped_to_company(db_session):
    repo = Repository(db_session)

    company_a = repo.create_company(name="A")
    company_b = repo.create_company(name="B")
    repo.create_project(company_a.id, name="A1")
    repo.create_project(company_b.id, name="B1")

    assert [p.name for p in repo.list_projects(company_a.id)] == ["A1"]


def test_hypothesis_crud_and_status_update(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    hypothesis = repo.create_hypothesis(
        project_id=project.id,
        statement="COGS growth is driven by a supplier price increase.",
        status="PLAUSIBLE",
        data_required="Supplier invoices for the period.",
    )
    assert hypothesis.supporting_finding_ids == []  # default applied, not None

    updated = repo.update_hypothesis(hypothesis.id, status="CONFIRMED", supporting_finding_ids=[1, 2])
    assert updated.status == "CONFIRMED"
    assert updated.supporting_finding_ids == [1, 2]

    assert [h.statement for h in repo.list_hypotheses(project.id)] == [hypothesis.statement]


def test_update_hypothesis_can_clear_a_field_to_null(db_session):
    """Regression: an explicit None used to be silently skipped, so a PATCH
    intended to clear a field left the old value in place."""
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    hypothesis = repo.create_hypothesis(
        project_id=project.id, statement="X", priority="HIGH", data_required="Invoices"
    )

    cleared = repo.update_hypothesis(hypothesis.id, priority=None)

    assert cleared.priority is None
    assert cleared.data_required == "Invoices"  # untouched field survives


def test_concern_and_opportunity_crud(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    repo.create_concern(project_id=project.id, title="Margin compression", severity="HIGH", confidence="HIGH")
    assert len(repo.list_concerns(project.id)) == 1
    repo.clear_concerns(project.id)
    assert repo.list_concerns(project.id) == []

    repo.create_opportunity(
        project_id=project.id, title="Cost efficiency", rationale="Opex ratio improving.", confidence="MEDIUM"
    )
    assert len(repo.list_opportunities(project.id)) == 1
    repo.clear_opportunities(project.id)
    assert repo.list_opportunities(project.id) == []


def test_list_concerns_prioritized_by_severity_not_creation_order(db_session):
    """Spec section 15 Phase 2 / Deep Analysis mode step 10: concerns must be
    shown prioritized. Create the least urgent one first to prove this is
    sorting by severity, not accidentally matching creation order."""
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    repo.create_concern(project_id=project.id, title="Low priority", severity="LOW", confidence="LOW")
    repo.create_concern(project_id=project.id, title="Critical", severity="CRITICAL", confidence="HIGH")
    repo.create_concern(project_id=project.id, title="Medium", severity="MEDIUM", confidence="MEDIUM")
    repo.create_concern(project_id=project.id, title="High", severity="HIGH", confidence="HIGH")

    titles = [c.title for c in repo.list_concerns(project.id)]
    assert titles == ["Critical", "High", "Medium", "Low priority"]


def test_list_opportunities_prioritized_by_confidence(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")

    repo.create_opportunity(project_id=project.id, title="Low", rationale="x", confidence="LOW")
    repo.create_opportunity(project_id=project.id, title="High", rationale="x", confidence="HIGH")
    repo.create_opportunity(project_id=project.id, title="Medium", rationale="x", confidence="MEDIUM")

    titles = [o.title for o in repo.list_opportunities(project.id)]
    assert titles == ["High", "Medium", "Low"]
