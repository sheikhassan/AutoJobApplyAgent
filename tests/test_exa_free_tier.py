from app.exa_search import SOURCES, SOURCE_QUERIES, DEFAULT_MAX_RESULTS, DEFAULT_QUERY_BUDGET

def test_free_tier_defaults():
    assert DEFAULT_MAX_RESULTS == 5
    assert DEFAULT_QUERY_BUDGET == 8

def test_job_source_universe_includes_requested_platforms():
    names = {s.name for s in SOURCES}
    for expected in {"HiringCafe", "LinkedIn Jobs", "Indeed", "Wellfound", "Greenhouse", "Lever", "Ashby", "Mercor", "micro1", "Randstad", "Michael Page", "Quess Global Mobility", "Manpower First", "BCM Group", "Ambe International", "Abroseas"}:
        assert expected in names

def test_source_queries_cover_platforms_and_remote_hybrid():
    text = " ".join(SOURCE_QUERIES).lower()
    for term in ["hiringcafe", "linkedin", "indeed", "wellfound", "greenhouse", "lever", "ashby", "mercor", "micro1", "randstad", "michaelpage", "quesscorp", "manpowerfirst", "bcmgroup", "ambeinter", "abroseas", "hybrid"]:
        assert term in text
