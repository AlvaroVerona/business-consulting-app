"""Shared setup for report-generator tests (PDF/PPTX/Excel) — not a test
module itself (no test_ prefix), so pytest won't collect it."""

from src.database.repository import Repository
from src.services.financial_analysis_service import FinancialAnalysisService


def seed_full_project(repo: Repository) -> int:
    company = repo.create_company(name="Acme Wine Bar", industry="hospitality")
    project = repo.create_project(company.id, name="2026 Diagnostic")
    document = repo.create_document(project.id, filename="pnl.csv", file_type="csv", storage_path="/tmp/pnl.csv")
    repo.add_chunks(
        document.id,
        [
            {"content": "month: Jan; revenue: 10000; cogs: 4000; opex: 3000"},
            {"content": "month: Feb; revenue: 10000; cogs: 5500; opex: 2500"},
            {"content": "month: Mar; revenue: 10000; cogs: 7000; opex: 2000"},
        ],
    )
    analysis = FinancialAnalysisService(repo).run(project.id)

    concern = repo.create_concern(
        project_id=project.id,
        title="Gross margin compression",
        severity="HIGH",
        confidence="HIGH",
        business_impact="Gross margin fell 30 points.",
        evidence_finding_ids=[f.id for f in analysis.findings],
        recommended_action="Break down COGS by supplier.",
    )
    opportunity = repo.create_opportunity(
        project_id=project.id,
        title="Operating cost efficiency improving",
        rationale="Opex ratio fell from 30% to 20%.",
        confidence="MEDIUM",
        next_step="Confirm the driver is structural.",
    )
    hypothesis = repo.create_hypothesis(
        project_id=project.id,
        statement="Supplier prices rose.",
        status="PLAUSIBLE",
        data_required="Supplier invoices.",
        origin="agent",
    )
    repo.update_concern(concern.id, root_cause_hypothesis_ids=[hypothesis.id])

    repo.create_business_profile(
        project_id=project.id,
        business_model="Single-location wine bar.",
        confidence="LOW",
        missing_information=["No customer data."],
    )

    run = repo.create_deep_analysis_run(project.id)
    repo.complete_deep_analysis_run(
        run.id,
        executive_summary={
            "overall_assessment": "Gross margin is compressing due to rising COGS.",
            "key_findings": ["Gross margin fell from 60% to 30%."],
            "concern_ids": [concern.id],
            "opportunity_ids": [opportunity.id],
            "business_performance": {
                "revenue": "Flat at $10,000/month.",
                "growth": "0% period over period.",
                "margin": "Declining, from 60% to 30%.",
                "cash": "Not covered in the documents provided.",
                "key_operational_metrics": ["Opex ratio improved from 30% to 20%."],
            },
            "strategic_options": [
                {
                    "option": "Renegotiate the primary wine supplier contract.",
                    "upside": "Could recover 5-10 points of gross margin.",
                    "downside": "May strain the supplier relationship.",
                    "investment": "Management time only.",
                    "feasibility": "MEDIUM",
                    "risks": "Supplier may not agree to better terms.",
                    "recommendation": "Pursue within 30 days.",
                }
            ],
            "ninety_day_plan": [
                {
                    "action": "Break down COGS by supplier and SKU.",
                    "data_requirements": "Itemized COGS ledger.",
                    "decision_needed": None,
                    "kpi": "Gross margin %",
                    "expected_impact": "Identify the specific driver of the COGS increase.",
                }
            ],
            "missing_information": ["No customer or market data ingested."],
        },
        quality_issues=[],
    )

    return project.id
