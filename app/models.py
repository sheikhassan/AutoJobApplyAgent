from pydantic import BaseModel, Field
from typing import Optional

class Job(BaseModel):
    title: str
    company: str = ""
    url: str
    source_title: str = ""
    source_category: str = ""
    location: str = ""
    work_mode: str = "unknown"
    salary: str = ""
    currency: str = ""
    description: str = ""
    requirements: list[str] = Field(default_factory=list)
    cover_letter_required: Optional[bool] = None
    application_url: str = ""
    contact_emails: list[str] = Field(default_factory=list)
    contact_phones: list[str] = Field(default_factory=list)
    years_experience_required: float | None = None
    sponsorship: str = "unknown"
    eligibility_note: str = ""
    posted_date: str = ""
    search_query: str = ""
    match_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

class ApplicationPackage(BaseModel):
    job_url: str
    company: str
    role: str
    match_score: float
    tailored_resume: str
    cover_letter: str = ""
    application_notes: str = ""
    needs_human_review: bool = True
    review_status: str = "pending"
