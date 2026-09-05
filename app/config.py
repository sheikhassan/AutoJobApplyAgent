from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class JobConfig:
    roles: list[str] = field(default_factory=lambda: [
        "AI Engineer", "AI/ML Engineer", "Agentic AI Engineer",
        "AI Software Engineer", "AI Software Developer",
        "Generative AI Engineer", "LLM Engineer",
        "Machine Learning Engineer", "Software Development Engineer",
        "Backend Engineer AI", "Deep Learning Engineer", "NLP Engineer",
        "Computer Vision Engineer", "ML Platform Engineer", "AI Platform Engineer",
        "LLM Application Engineer", "AI Infrastructure Engineer"
    ])
    preferred_modes: list[str] = field(default_factory=lambda: ["remote", "hybrid"])
    preferred_currencies: list[str] = field(default_factory=lambda: ["USD", "EUR", "AED", "SAR"])
    remote_weight: float = 1.0
    hybrid_weight: float = 0.85
    currency_weight: float = 0.75
    min_match_score: float = 0.60
    candidate_experience_years: float = 2.0
    max_acceptable_experience_years: float = 3.0
    international_recruiters_enabled: bool = True
    exa_num_results: int = 10

def exa_api_key() -> str:
    key = os.getenv("EXA_API_KEY", "")
    if not key:
        raise RuntimeError("EXA_API_KEY is not set. Copy .env.example to .env and add your key.")
    return key

def validate_production():
    required=['DATABASE_URL','DASHBOARD_PASSWORD','DASHBOARD_SESSION_SECRET','NOTIFY_TO']
    missing=[k for k in required if not os.getenv(k)]
    if missing: raise RuntimeError('Missing production settings: '+', '.join(missing))
    if len(os.getenv('DASHBOARD_SESSION_SECRET',''))<32: raise RuntimeError('DASHBOARD_SESSION_SECRET must be at least 32 characters')
    if os.getenv('REQUIRE_HTTPS','true').lower() in {'1','true','yes'} and os.getenv('COOKIE_SECURE','true').lower() not in {'1','true','yes'}:
        raise RuntimeError('COOKIE_SECURE=true is required when REQUIRE_HTTPS=true')
    if os.getenv('RATE_LIMIT_ENABLED','true').lower() in {'1','true','yes'} and not os.getenv('REDIS_URL'):
        raise RuntimeError('REDIS_URL is required for production rate limiting')
    if os.getenv('AUTH_REQUIRED','true').lower() not in {'1','true','yes'}:
        raise RuntimeError('AUTH_REQUIRED=true is required for production')
