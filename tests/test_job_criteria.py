from app.config import JobConfig
from app.matcher import score_job
from app.models import Job


def test_three_year_requirement_is_accepted_for_two_year_candidate():
    job=Job(title='AI Engineer',url='https://example.com/job',description='Requires 3 years of relevant experience. Remote. Python LangGraph.')
    score_job(job)
    assert job.years_experience_required == 3
    assert 'Accepted' in job.eligibility_note
    assert not any('outside' in g for g in job.gaps)


def test_more_than_three_years_is_not_qualified():
    job=Job(title='Senior AI Engineer',url='https://example.com/job2',description='Requires 5 years of experience. Remote.')
    score_job(job)
    assert job.years_experience_required == 5
    assert job.match_score < 0.5
    assert job.gaps


def test_missing_experience_requirement_remains_eligible():
    job=Job(title='AI Engineer',url='https://example.com/job3',description='Remote Python LangGraph role.')
    score_job(job)
    assert job.years_experience_required is None
    assert 'apply if the role otherwise matches' in job.eligibility_note
    assert not job.gaps


def test_inr_is_lowest_currency_preference():
    from app.pipeline import _currency_priority
    assert _currency_priority('USD') > _currency_priority('EUR') > _currency_priority('AED') > _currency_priority('SAR')
    assert _currency_priority('SAR') > _currency_priority('INR')


def test_job_api_orders_preferred_currencies_before_inr():
    from pathlib import Path
    api = Path(__file__).parents[1].joinpath('app', 'api.py').read_text()
    assert "WHEN 'USD' THEN 5" in api
    assert "WHEN 'EUR' THEN 4" in api
    assert "WHEN 'AED' THEN 3" in api
    assert "WHEN 'SAR' THEN 2" in api
    assert "WHEN 'INR' THEN 0" in api


def test_ai_engineering_keyword_queries_are_present():
    from app.exa_search import AI_KEYWORD_QUERY_GROUPS, AI_ENGINEERING_KEYWORDS, SOURCE_QUERIES
    keywords={k.lower() for k in AI_ENGINEERING_KEYWORDS}
    assert "deep learning" in keywords
    assert "transformers" in keywords
    assert "retrieval-augmented generation" in keywords
    assert "quantization" in keywords
    assert any("guardrails" in q.lower() for q in AI_KEYWORD_QUERY_GROUPS)
    assert any("inference pipeline" in q.lower() for q in AI_KEYWORD_QUERY_GROUPS)

def test_keyword_relevance_is_only_a_match_signal():
    from app.models import Job
    j=Job(title="LLM Engineer", url="https://example.com/llm", description="Remote role using transformers, RAG, vector databases, prompt engineering, guardrails and inference pipelines.")
    score_job(j)
    assert any("keyword coverage" in r.lower() for r in j.reasons)
    assert not any("PyTorch" in r for r in j.reasons)
