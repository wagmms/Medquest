import uuid
import pytest
from api.auth import is_valid_uuid_v4

def test_is_valid_uuid_v4_valid_lowercase():
    # Valid v4
    val = str(uuid.uuid4())
    assert is_valid_uuid_v4(val) is True

def test_is_valid_uuid_v4_valid_uppercase():
    # Valid v4, uppercased (the function currently accepts this due to val.lower())
    val = str(uuid.uuid4()).upper()
    assert is_valid_uuid_v4(val) is True

def test_is_valid_uuid_v4_nil_uuid():
    # Nil UUID is explicitly rejected
    nil_uuid = "00000000-0000-0000-0000-000000000000"
    assert is_valid_uuid_v4(nil_uuid) is False

def test_is_valid_uuid_v4_wrong_version():
    # v1 UUID
    val_v1 = str(uuid.uuid1())
    assert is_valid_uuid_v4(val_v1) is False

    # v3 UUID
    val_v3 = str(uuid.uuid3(uuid.NAMESPACE_DNS, "example.com"))
    assert is_valid_uuid_v4(val_v3) is False

    # v5 UUID
    val_v5 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))
    assert is_valid_uuid_v4(val_v5) is False

def test_is_valid_uuid_v4_malformed_string():
    assert is_valid_uuid_v4("not-a-uuid") is False
    assert is_valid_uuid_v4("12345678-1234-1234-1234-12345678901") is False # Too short
    assert is_valid_uuid_v4("12345678-1234-1234-1234-1234567890123") is False # Too long

def test_is_valid_uuid_v4_missing_dashes():
    # Valid UUID but missing dashes
    val = uuid.uuid4().hex
    assert is_valid_uuid_v4(val) is False

def test_is_valid_uuid_v4_invalid_types():
    assert is_valid_uuid_v4(None) is False
    assert is_valid_uuid_v4(123) is False
    assert is_valid_uuid_v4([]) is False
    assert is_valid_uuid_v4({}) is False

def test_is_valid_uuid_v4_empty_string():
    assert is_valid_uuid_v4("") is False

def test_is_valid_uuid_v4_only_dashes():
    assert is_valid_uuid_v4("------------------------------------") is False
