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


def test_list_projects_scoped_to_company(db_session):
    repo = Repository(db_session)

    company_a = repo.create_company(name="A")
    company_b = repo.create_company(name="B")
    repo.create_project(company_a.id, name="A1")
    repo.create_project(company_b.id, name="B1")

    assert [p.name for p in repo.list_projects(company_a.id)] == ["A1"]
