import re
from urllib.parse import urlsplit, urlunsplit
from .models import Job

def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", p.path)
    return urlunsplit((p.scheme.lower() or "https", host, path, "", ""))

def infer_mode(text: str) -> str:
    t = text.lower()
    if "hybrid" in t: return "hybrid"
    if "remote" in t or "work from home" in t: return "remote"
    return "unknown"

def infer_currency(text: str) -> str:
    t = text.lower()
    if "$" in t or " usd" in t or "us dollar" in t: return "USD"
    if "€" in t or " eur" in t or "euro" in t: return "EUR"
    if "aed" in t or "dirham" in t: return "AED"
    if "sar" in t or "riy" in t: return "SAR"
    return ""

def normalize(job: Job) -> Job:
    combined = " ".join([job.title, job.description, job.location, job.salary])
    job.url = canonical_url(job.url)
    job.work_mode = infer_mode(combined)
    job.currency = infer_currency(combined)
    return job

def dedupe(jobs: list[Job]) -> list[Job]:
    seen = set()
    out = []
    for j in jobs:
        j = normalize(j)
        key = j.url or (j.company.lower(), j.title.lower())
        if key in seen: continue
        seen.add(key)
        out.append(j)
    return out
