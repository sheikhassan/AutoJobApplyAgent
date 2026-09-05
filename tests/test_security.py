import os
import pytest
from app.security import validate_external_url, SecurityError, new_csrf_token

def test_rejects_non_http():
    with pytest.raises(SecurityError): validate_external_url('javascript:alert(1)')

def test_rejects_localhost():
    with pytest.raises(SecurityError): validate_external_url('http://localhost:8000')

def test_rejects_private_ip():
    with pytest.raises(SecurityError): validate_external_url('http://127.0.0.1/')

def test_csrf_token_is_unpredictable():
    a,b=new_csrf_token(),new_csrf_token()
    assert len(a) >= 32 and a != b
