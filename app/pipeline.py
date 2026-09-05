import json
import os
import re
from pathlib import Path
from .config import JobConfig
from .exa_search import DEFAULT_CONTENTS_LIMIT, DEFAULT_MAX_RESULTS, DEFAULT_QUERY_BUDGET
from .search_router import SearchRouter
from .normalize import dedupe
from .matcher import score_job
from .model_provider import LoadBalancedModelProvider, StubModelProvider
from .models import Job
from .database import init_db, save_run
from .security import validate_external_url, SecurityError
from .cold_outreach import extract_public_emails


def _currency_priority(currency: str) -> int:
    # Explicit user preference: USD, EUR, AED, SAR first; INR last.
    return {"USD": 5, "EUR": 4, "AED": 3, "SAR": 2, "INR": 0}.get((currency or "").upper(), 1)


def _infer_work_mode(text: str) -> str:
    t=text.lower()
    if re.search(r"\b(remote|work from home|wfh|fully remote|100% remote)\b", t): return "remote"
    if re.search(r"\b(hybrid|flexible workplace|partly remote)\b", t): return "hybrid"
    if re.search(r"\b(on[- ]site|onsite|office based|in office)\b", t): return "onsite"
    return "unknown"


def _infer_currency(text: str) -> str:
    t=text.upper()
    for code in ("USD","EUR","AED","SAR"):
        if re.search(rf"\b{code}\b", t): return code
    if "$" in text: return "USD"
    if "€" in text: return "EUR"
    return ""


def _to_job(raw: dict) -> Job | None:
    highlights = raw.get("highlights") or []
    description = "\n".join(highlights) if isinstance(highlights, list) else str(highlights)
    raw_text = " ".join([str(raw.get("title", "")), description, str(raw.get("snippet", ""))])
    try:
        safe_url=validate_external_url(str(raw.get('url','')))
    except SecurityError:
        return None
    return Job(
        title=str(raw.get("title", "") or "Untitled role")[:500],
        url=safe_url,
        source_title=raw.get("source", ""),
        source_category=raw.get("source_category", ""),
        description=description,
        search_query=raw.get("search_query", ""),
        posted_date=raw.get("published_date", "") or "",
        application_url=safe_url,
        contact_emails=extract_public_emails(raw_text),
        sponsorship=str(raw.get("sponsorship", "unknown") or "unknown"),
        work_mode=_infer_work_mode(raw_text),
        currency=_infer_currency(raw_text),
        salary=str(raw.get("salary", "") or ""),
    )


def run(config: JobConfig, max_queries: int | None = None, results_per_query: int | None = None):
    init_db()
    router = SearchRouter(config)
    query_budget = max_queries or DEFAULT_QUERY_BUDGET
    per_query = results_per_query or DEFAULT_MAX_RESULTS
    if router.primary:
        queries = router.primary.queries()[:query_budget]
    else:
        queries = [
            '"AI Engineer" remote jobs', '"AI/ML Engineer" remote jobs', '"Agentic AI Engineer" remote jobs',
            '"LLM Engineer" remote jobs', '"Generative AI Engineer" remote jobs', '"Machine Learning Engineer" remote jobs',
            '"AI Software Engineer" remote jobs', '"Backend Engineer" AI Python Java remote jobs'
        ][:query_budget]

    raw_jobs, search_provider, search_warning = router.search_jobs(queries, per_query, query_budget)

    jobs = dedupe([j for j in (_to_job(x) for x in raw_jobs) if j is not None])
    scored = [score_job(j) for j in jobs]
    # Remote first, hybrid second. On-site roles are retained only when the
    # source does not expose a work mode; explicitly on-site roles are excluded
    # because the configured search objective is remote/hybrid.
    jobs = [j for j in scored if j.work_mode in {"remote", "hybrid", "unknown"}]
    jobs = [j for j in jobs if j.years_experience_required is None or j.years_experience_required <= config.max_acceptable_experience_years]
    jobs.sort(key=lambda x: (
        x.work_mode == "remote",
        x.work_mode == "hybrid",
        _currency_priority(x.currency),
        x.match_score,
    ), reverse=True)

    # Only retrieve broader page content for the best candidates, preserving
    # the free-tier-first discovery strategy.
    shortlist = [j for j in jobs if j.match_score >= config.min_match_score][:DEFAULT_CONTENTS_LIMIT]
    try:
        contents = router.fetch_contents([j.url for j in shortlist], DEFAULT_CONTENTS_LIMIT)
        for job in shortlist:
            if job.url in contents and contents[job.url]:
                job.description = contents[job.url]
                # Contact details may only appear on the full source page, not the search snippet.
                job.contact_emails = extract_public_emails(job.description)[:10]
                jobs[jobs.index(job)] = score_job(job)
    except Exception:
        contents = {}

    use_model = os.getenv("USE_MODEL", "true").lower() in {"1", "true", "yes"}
    provider = LoadBalancedModelProvider() if use_model else StubModelProvider()
    package_limit = int(os.getenv("MAX_PACKAGES_PER_RUN", "10"))
    packages = [provider.build_application_package(j) for j in jobs if j.match_score >= config.min_match_score][:package_limit]

    outreach_results=[]
    if os.getenv("COLD_OUTREACH_ENABLED", "false").lower() in {"1","true","yes"}:
        try:
            from .cold_outreach import send_cold_outreach
            for j in jobs:
                if j.match_score < config.min_match_score or not j.contact_emails:
                    continue
                result=send_cold_outreach(j, provider=provider)
                outreach_results.append({"job_url":j.url, **result})
        except Exception as exc:
            outreach_results.append({"status":"failed","error":str(exc)[:500]})

    out = Path("outputs")
    out.mkdir(exist_ok=True)
    (out / "jobs.json").write_text(json.dumps([j.model_dump() for j in jobs], indent=2), encoding="utf-8")
    (out / "application_queue.json").write_text(json.dumps([p.model_dump() for p in packages], indent=2), encoding="utf-8")
    report = {
        "queries_run": queries,
        "jobs_found": len(jobs),
        "qualified": len(packages),
        "content_pages_fetched": len(contents),
        "source_universe": "job boards + ATS + AI talent networks + company career pages",
        "auto_apply": False,
        "search_provider": search_provider,
        "search_warning": search_warning,
        "cold_outreach_enabled": os.getenv("COLD_OUTREACH_ENABLED", "false").lower() in {"1","true","yes"},
        "cold_outreach": outreach_results,
    }
    (out / "run_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    save_run(jobs, packages, report)
    return jobs, packages
