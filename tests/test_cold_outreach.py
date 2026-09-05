from app.cold_outreach import extract_public_emails

def test_extracts_public_email_and_dedupes():
    text = "Contact recruiter@example.org or recruiter@example.org; do not use noreply@example.org"
    assert extract_public_emails(text) == ["recruiter@example.org"]

def test_ignores_noreply():
    assert extract_public_emails("noreply@example.org") == []
