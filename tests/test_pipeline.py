from app.normalize import canonical_url, dedupe
from app.models import Job
from app.matcher import score_job

def test_canonical_url():
    assert canonical_url("https://WWW.Example.com/jobs/123/?utm_source=x") == "https://example.com/jobs/123"

def test_dedupe():
    jobs = [
        Job(title="AI Engineer", url="https://example.com/a/"),
        Job(title="AI Engineer", url="https://example.com/a"),
    ]
    assert len(dedupe(jobs)) == 1

def test_langgraph_is_strong_signal():
    j = Job(title="Agentic AI Engineer", url="https://example.com/j", description="Build multi-agent LLM systems with Python and LangGraph")
    j = score_job(j)
    assert any("LangGraph" in x for x in j.reasons)
    assert j.match_score > 0
