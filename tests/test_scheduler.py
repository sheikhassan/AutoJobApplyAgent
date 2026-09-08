import os
from unittest.mock import patch
import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.testclient import TestClient
from app.scheduler import setup_scheduler, get_scheduler_info, get_configured_times
from app.api import app


def test_get_configured_times(monkeypatch):
    monkeypatch.setenv('JOB_HUNTER_TIMES', '06:00, 08:00, 13:00, 22:00, 00:00')
    times = get_configured_times()
    assert times == ['06:00', '08:00', '13:00', '22:00', '00:00']


def test_setup_scheduler_registers_all_jobs(monkeypatch):
    monkeypatch.setenv('JOB_HUNTER_TIMES', '06:00,08:00,13:00,22:00,00:00')
    monkeypatch.setenv('JOB_HUNTER_TIMEZONE', 'Asia/Kolkata')
    sched = BackgroundScheduler(timezone='Asia/Kolkata')
    setup_scheduler(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 5
    job_ids = [j.id for j in jobs]
    assert job_ids == ['job-hunter-0', 'job-hunter-1', 'job-hunter-2', 'job-hunter-3', 'job-hunter-4']


def test_scheduler_info_live_calculation(monkeypatch):
    monkeypatch.setenv('JOB_HUNTER_TIMES', '06:00,08:00,13:00,22:00,00:00')
    monkeypatch.setenv('JOB_HUNTER_TIMEZONE', 'Asia/Kolkata')
    sched = BackgroundScheduler(timezone='Asia/Kolkata')
    setup_scheduler(sched)
    sched.start()
    try:
        info = get_scheduler_info(sched)
        assert info['running'] is True
        assert info['timezone'] == 'Asia/Kolkata'
        assert len(info['schedule_times']) == 5
        assert info['next_run_time'] is not None
        assert 'T' in info['next_run_time']
    finally:
        sched.shutdown(wait=False)


def test_cron_endpoint_rejects_unauthorized():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post('/api/cron/run')
    assert resp.status_code == 401


def test_cron_endpoint_accepts_valid_secret(monkeypatch):
    monkeypatch.setenv('CRON_SECRET', 'test-secret-with-sufficient-length-32-chars!')
    client = TestClient(app)
    with patch('app.scheduler.run_scheduled_scan') as mock_scan:
        resp = client.post('/api/cron/run', headers={'X-Cron-Secret': 'test-secret-with-sufficient-length-32-chars!'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['status'] == 'triggered'


def test_scheduler_status_endpoint():
    client = TestClient(app)
    resp = client.get('/api/scheduler/status')
    assert resp.status_code == 200
    data = resp.json()
    assert 'running' in data
    assert 'timezone' in data
    assert 'schedule_times' in data
