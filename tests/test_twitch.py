import pytest
from unittest.mock import MagicMock
from twitch import add_sub_time

def test_add_sub_time_tier_1():
    obs_thread_mock = MagicMock()
    add_sub_time.obs_thread = obs_thread_mock
    add_sub_time('1000')
    obs_thread_mock.add_time.assert_called_once()

def test_add_sub_time_tier_2():
    obs_thread_mock = MagicMock()
    add_sub_time.obs_thread = obs_thread_mock
    add_sub_time('2000')
    obs_thread_mock.add_time.assert_called_once()

def test_add_sub_time_tier_3():
    obs_thread_mock = MagicMock()
    add_sub_time.obs_thread = obs_thread_mock
    add_sub_time('3000')
    obs_thread_mock.add_time.assert_called_once()

def test_add_sub_time_invalid_tier():
    with pytest.raises(Exception):
        add_sub_time('4000')