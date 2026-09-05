import re
from .models import Job
from .resume_profile import MASTER_RESUME
from .exa_search import AI_ENGINEERING_KEYWORDS

def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9+#.-]{2,}", text.lower()))

def resume_text() -> str:
    parts = [MASTER_RESUME["headline"], MASTER_RESUME["summary"]]
    for e in MASTER_RESUME["experience"]:
        parts += [e["title"], e["company"]] + e["evidence"]
    for p in MASTER_RESUME["projects"]:
        parts += [p["name"]] + p["evidence"]
    for vals in MASTER_RESUME["skills"].values():
        parts += vals
    return " ".join(parts)

def _required_years(text: str) -> float | None:
    patterns = [
        r"(?:at least|minimum of|minimum|more than|over)\s+(\d+(?:\.\d+)?)\s*\+?\s*years?",
        r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of|professional|relevant)",
    ]
    vals=[]
    for pat in patterns:
        vals += [float(x) for x in re.findall(pat, text, flags=re.I)]
    return max(vals) if vals else None


def _currency_priority(currency: str, preferred: list[str] | None = None) -> int:
    """Higher is better. Preferred order is USD > EUR > AED > SAR; INR is last."""
    order = preferred or ["USD", "EUR", "AED", "SAR"]
    c = (currency or "").upper()
    if c == "INR":
        return 0
    if c in order:
        return len(order) + 2 - order.index(c)
    return 1  # Unknown/non-INR currencies are kept but ranked below preferred currencies.

def score_job(job: Job) -> Job:
    jd = " ".join([job.title, job.description, " ".join(job.requirements)]).lower()
    rt = tokens(resume_text())
    jt = tokens(jd)
    overlap = len(rt & jt) / max(1, len(jt))
    role_bonus = 0.20 if any(x.lower() in job.title.lower() for x in [
        "ai engineer", "machine learning", "genai", "generative ai",
        "llm", "agentic", "software engineer", "sde"
    ]) else 0.0
    # Modest discovery relevance boost; keyword presence is not a claim of candidate proficiency.
    keyword_hits = sum(1 for k in AI_ENGINEERING_KEYWORDS if k.lower() in jd)
    keyword_bonus = min(0.08, keyword_hits * 0.01)
    mode_bonus = 0.12 if job.work_mode == "remote" else (0.06 if job.work_mode == "hybrid" else -0.12)
    currency_bonus = 0.09 if job.currency in {"USD","EUR","AED","SAR"} else (-0.03 if job.currency == "INR" else 0.0)
    req = _required_years(jd)
    job.years_experience_required = req
    if req is not None:
        if req <= 2:
            job.eligibility_note = "Experience requirement is within the candidate's 2 years."
            exp_bonus = 0.05
        elif req <= 3:
            job.eligibility_note = "Accepted: employer asks for up to 3 years; candidate has 2 years. Review role seniority before applying."
            exp_bonus = 0.015
        else:
            job.eligibility_note = f"Employer asks for about {req:g}+ years; outside the configured 2–3 year tolerance."
            exp_bonus = -0.20
            job.gaps.append(job.eligibility_note)
    else:
        # Missing experience requirements must never be treated as a rejection.
        # Keep the role eligible and let the overall skill/location match decide.
        job.eligibility_note = "No experience requirement stated; apply if the role otherwise matches the candidate profile."
        exp_bonus = 0.0
    score = min(1.0, max(0.0, 0.57 * overlap + role_bonus + mode_bonus + currency_bonus + exp_bonus + keyword_bonus))
    job.match_score = round(score, 3)
    if keyword_hits >= 3:
        job.reasons.append(f"AI engineering keyword coverage: {keyword_hits} relevant concepts found in the JD.")
    if "langgraph" in jd and "langgraph" in rt:
        job.reasons.append("Direct LangGraph experience in VentureGPT.")
    if "multi-agent" in jd or "multi agent" in jd:
        job.reasons.append("Direct multi-agent workflow experience.")
    if "python" in jd and "python" in rt:
        job.reasons.append("Python is a demonstrated skill.")
    if job.work_mode == "remote":
        job.reasons.append("Remote-first preference match.")
    elif job.work_mode == "hybrid":
        job.reasons.append("Hybrid is the accepted secondary preference.")
    if req is not None and req <= 3:
        job.reasons.append("2 years of experience accepted against a configured tolerance up to 3 years.")
    return job
