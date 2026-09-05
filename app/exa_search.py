import os
from dataclasses import dataclass
from typing import Iterable

# Exa is the discovery layer. We deliberately keep the query budget small for
# the free tier and use highlights first; full page contents are only fetched
# for shortlisted URLs.
DEFAULT_MAX_RESULTS = int(os.getenv("EXA_MAX_RESULTS_PER_QUERY", "5"))
DEFAULT_QUERY_BUDGET = int(os.getenv("EXA_QUERY_BUDGET", "8"))
DEFAULT_CONTENTS_LIMIT = int(os.getenv("EXA_CONTENTS_LIMIT", "5"))

@dataclass(frozen=True)
class SearchSource:
    name: str
    category: str
    domains: tuple[str, ...] = ()

SOURCES = [
    SearchSource("HiringCafe", "job_board", ("hiringcafe.com",)),
    SearchSource("LinkedIn Jobs", "job_board", ("linkedin.com",)),
    SearchSource("Indeed", "job_board", ("indeed.com",)),
    SearchSource("Wellfound", "job_board", ("wellfound.com",)),
    SearchSource("Greenhouse", "ats", ("greenhouse.io",)),
    SearchSource("Lever", "ats", ("lever.co",)),
    SearchSource("Ashby", "ats", ("ashbyhq.com",)),
    SearchSource("Workday", "ats", ("myworkdayjobs.com",)),
    SearchSource("SmartRecruiters", "ats", ("smartrecruiters.com",)),
    SearchSource("Company Careers", "direct", ()),
    SearchSource("Mercor", "ai_network", ("mercor.com",)),
    SearchSource("micro1", "ai_network", ("micro1.ai",)),
    SearchSource("Y Combinator Jobs", "job_board", ("ycombinator.com",)),
    SearchSource("Dice", "job_board", ("dice.com",)),
    # Legitimate international recruiters / overseas staffing sources supplied
    # by the candidate. These are searched as vacancy sources, not treated as
    # proof that any individual role has sponsorship or is scam-free.
    SearchSource("Randstad", "recruiter", ("randstad.in",)),
    SearchSource("Michael Page", "recruiter", ("michaelpage.co.in",)),
    SearchSource("Quess Global Mobility", "recruiter", ("quesscorp.com",)),
    SearchSource("Manpower First", "recruiter", ("manpowerfirst.com",)),
    SearchSource("BCM Group", "recruiter", ("bcmgroup.in",)),
    SearchSource("Ambe International", "recruiter", ("ambeinter.com",)),
    SearchSource("Abroseas", "recruiter", ("abroseas.com",)),
]


# AI/ML engineering keyword universe used to broaden discovery and improve recall.
# These are search/matching terms, not claims that the candidate has every skill.
AI_ENGINEERING_KEYWORDS = [
    "deep learning", "transformers", "fine-tuning", "quantization",
    "retrieval-augmented generation", "RAG", "vector databases",
    "prompt engineering", "semantic search", "orchestration", "guardrails",
    "inference pipeline", "hyperparameters", "API integration",
    "deterministic code", "stochastic systems", "embeddings", "reranking",
    "evaluation", "LLM evaluation", "model serving", "inference",
    "MLOps", "machine learning pipelines", "feature engineering",
    "PyTorch", "TensorFlow", "Hugging Face", "vLLM", "Triton",
    "LangChain", "LangGraph", "agents", "multi-agent", "tool calling",
    "function calling", "structured outputs", "Pydantic", "FastAPI",
    "Python", "REST API", "microservices", "PostgreSQL", "Redis",
    "Qdrant", "HNSW", "Docker", "Kubernetes", "AWS", "Azure",
    "CI/CD", "observability", "monitoring", "testing", "security",
    "RBAC", "OAuth", "JWT", "data pipelines", "NLP", "computer vision",
]

AI_KEYWORD_QUERY_GROUPS = [
    '"deep learning" transformers "fine-tuning" quantization',
    '"RAG" "retrieval-augmented generation" "vector database" embeddings',
    '"prompt engineering" "semantic search" orchestration guardrails',
    '"inference pipeline" hyperparameters "model serving" MLOps',
    '"LangGraph" agents "tool calling" "structured outputs"',
    '"PyTorch" "Hugging Face" transformers "LLM"',
    '"FastAPI" Python "REST API" microservices AI',
    '"evaluation" "LLM evaluation" RAG AI engineer',
    '"deterministic code" stochastic systems AI',
]

ROLE_QUERIES = [
    '"AI Engineer" remote jobs',
    '"AI/ML Engineer" remote jobs',
    '"Agentic AI Engineer" remote jobs',
    '"LLM Engineer" remote jobs',
    '"Generative AI Engineer" remote jobs',
    '"Machine Learning Engineer" remote jobs',
    '"AI Software Engineer" remote jobs',
    '"Backend Engineer" AI Python Java remote jobs',
    '"Software Development Engineer" AI remote jobs',
]

RECRUITER_QUERIES = [
    'site:randstad.in AI Engineer remote international jobs',
    'site:michaelpage.co.in AI ML software engineer international jobs',
    'site:quesscorp.com global mobility IT jobs India overseas',
    'site:manpowerfirst.com IT tech overseas jobs India',
    'site:bcmgroup.in IT jobs Europe India recruitment',
    'site:ambeinter.com IT overseas jobs India',
    'site:abroseas.com IT overseas jobs India',
]

SOURCE_QUERIES = [
    'AI Engineer remote jobs HiringCafe',
    'AI Engineer remote jobs LinkedIn',
    'AI Engineer remote jobs Indeed',
    'AI Engineer remote jobs Wellfound',
    'AI Engineer remote jobs Greenhouse Lever Ashby',
    'AI engineer remote Mercor micro1',
    'AI Engineer remote company careers',
    'AI Engineer hybrid jobs',
    *RECRUITER_QUERIES,
    *AI_KEYWORD_QUERY_GROUPS,
]

class ExaJobSearcher:
    def __init__(self, config=None, api_key: str | None = None):
        # Lazy import keeps unit tests runnable without exa-py installed.
        try:
            from exa_py import Exa
        except ImportError as exc:
            raise RuntimeError("exa-py is required at runtime. Install requirements.txt") from exc
        key = api_key or os.getenv("EXA_API_KEY")
        if not key:
            raise ValueError("EXA_API_KEY is required")
        self.client = Exa(api_key=key)
        self.config = config

    def queries(self) -> list[str]:
        return SOURCE_QUERIES + ROLE_QUERIES + AI_KEYWORD_QUERY_GROUPS

    def search(self, query: str, results_per_query: int = DEFAULT_MAX_RESULTS) -> list[dict]:
        # Source-specific searches are encoded in the query so we can stay on
        # Exa's normal web index without maintaining fragile per-site scrapers.
        kwargs = dict(
            type="auto",
            num_results=max(1, min(results_per_query, 10)),
            contents={"highlights": True},
        )
        domains = self.domains_for_query(query)
        if domains:
            kwargs["include_domains"] = domains
        response = self.client.search(query, **kwargs)
        jobs = []
        for result in getattr(response, "results", []):
            url = getattr(result, "url", None)
            if not url:
                continue
            source_name, source_category = self.source_metadata(url)
            jobs.append({
                "title": getattr(result, "title", "") or "",
                "url": url,
                "published_date": getattr(result, "published_date", None),
                "author": getattr(result, "author", None),
                "highlights": getattr(result, "highlights", None) or [],
                "search_query": query,
                "source": source_name,
                "source_category": source_category,
            })
        return jobs

    def search_jobs(self, queries: Iterable[str] | None = None,
                    max_results: int = DEFAULT_MAX_RESULTS,
                    query_budget: int = DEFAULT_QUERY_BUDGET) -> list[dict]:
        selected = list(queries or self.queries())[:max(1, query_budget)]
        seen: set[str] = set()
        jobs: list[dict] = []
        for query in selected:
            for job in self.search(query, max_results):
                key = job["url"].split("#", 1)[0].rstrip("/").lower()
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
        return jobs

    def fetch_contents(self, urls: list[str], limit: int = DEFAULT_CONTENTS_LIMIT) -> dict[str, str]:
        urls = list(dict.fromkeys(urls))[:max(0, limit)]
        if not urls:
            return {}
        response = self.client.get_contents(urls, highlights=True)
        out = {}
        for result in getattr(response, "results", []):
            url = getattr(result, "url", None)
            if url:
                highlights = getattr(result, "highlights", None) or []
                out[url] = "\n".join(highlights)
        return out

    @staticmethod
    def domains_for_query(query: str) -> list[str]:
        q = query.lower()
        for source in SOURCES:
            if source.domains and any(d.lower() in q for d in source.domains):
                return list(source.domains)
        return []

    @staticmethod
    def source_metadata(url: str) -> tuple[str, str]:
        host = url.lower().split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")
        for source in SOURCES:
            if any(host == d or host.endswith("." + d) for d in source.domains):
                return source.name, source.category
        return "Other / Company Career", "direct"

    @staticmethod
    def source_for_url(url: str) -> str:
        return ExaJobSearcher.source_metadata(url)[0]

# Backwards-compatible alias used by earlier versions.
ExaJobSearch = ExaJobSearcher
