import pytest
from api.webpush import is_host_allowed

def test_is_host_allowed_exact_match():
    assert is_host_allowed("example.com", ["example.com"]) is True
    assert is_host_allowed("api.example.com", ["api.example.com"]) is True

def test_is_host_allowed_wildcard():
    # Wildcard matches subdomains
    assert is_host_allowed("sub.example.com", ["*.example.com"]) is True
    assert is_host_allowed("a.b.example.com", ["*.example.com"]) is True

    # Wildcard matches base domain as well
    assert is_host_allowed("example.com", ["*.example.com"]) is True

def test_is_host_allowed_case_insensitivity_and_whitespace():
    assert is_host_allowed("Example.COM", ["example.com"]) is True
    assert is_host_allowed("example.com", ["EXAMPLE.COM"]) is True
    assert is_host_allowed("  example.com  ", ["example.com"]) is True
    assert is_host_allowed("example.com", ["  example.com  "]) is True
    assert is_host_allowed("  ExAmple.Com  ", ["  eXamPle.cOm  "]) is True

def test_is_host_allowed_empty_or_none():
    assert is_host_allowed("", ["example.com"]) is False
    assert is_host_allowed(None, ["example.com"]) is False
    assert is_host_allowed("example.com", []) is False
    assert is_host_allowed("example.com", None) is False

def test_is_host_allowed_empty_strings_in_patterns():
    assert is_host_allowed("example.com", ["", "example.com"]) is True
    assert is_host_allowed("example.com", ["   ", "example.com"]) is True
    assert is_host_allowed("example.com", [""]) is False
    assert is_host_allowed("example.com", ["   "]) is False

def test_is_host_allowed_false_matches():
    assert is_host_allowed("example.org", ["example.com"]) is False
    assert is_host_allowed("badexample.com", ["*.example.com"]) is False
    assert is_host_allowed("bad-example.com", ["example.com"]) is False
    assert is_host_allowed("example.com.org", ["example.com"]) is False
    assert is_host_allowed("sub.example.com", ["example.com"]) is False

def test_is_host_allowed_multiple_patterns():
    patterns = ["foo.com", "*.bar.com", "baz.org"]
    assert is_host_allowed("foo.com", patterns) is True
    assert is_host_allowed("sub.bar.com", patterns) is True
    assert is_host_allowed("bar.com", patterns) is True
    assert is_host_allowed("baz.org", patterns) is True
    assert is_host_allowed("other.com", patterns) is False
