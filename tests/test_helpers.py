import pytest
from helpers import fuzzy_strtime_to_int

def test_fuzzy_strtime_to_int_positive_integer():
    assert fuzzy_strtime_to_int("123") == 123

def test_fuzzy_strtime_to_int_negative_integer():
    assert fuzzy_strtime_to_int("-456") == -456

def test_fuzzy_strtime_to_int_simple_time():
    assert fuzzy_strtime_to_int("10:20") == 620

def test_fuzzy_strtime_to_int_full_time():
    assert fuzzy_strtime_to_int("1:23:45") == 5025

def test_fuzzy_strtime_to_int_negative_time():
    assert fuzzy_strtime_to_int("-0:05") == -5

def test_fuzzy_strtime_to_int_invalid_time_too_many_parts():
    assert fuzzy_strtime_to_int("1:2:3:4") == 0

def test_fuzzy_strtime_to_int_invalid_time_non_numeric():
    assert fuzzy_strtime_to_int("1:a:45") == 0

def test_fuzzy_strtime_to_int_empty_string():
    assert fuzzy_strtime_to_int("") == 0

def test_fuzzy_strtime_to_int_zero_seconds():
    assert fuzzy_strtime_to_int("0") == 0

def test_fuzzy_strtime_to_int_only_minutes():
    assert fuzzy_strtime_to_int("59:00") == 3540