import pytest
from unittest.mock import MagicMock
from obs import OBSThread

def test_update_time_success():
    obs_thread = OBSThread()
    obs_thread.get_time = MagicMock(return_value=60)
    obs_thread.set_time = MagicMock()
    obs_thread.remaining_time = 60

    obs_thread.update_time(10)

    obs_thread.get_time.assert_called_once()
    obs_thread.set_time.assert_called_once_with(70)

def test_update_time_value_error():
    obs_thread = OBSThread()
    obs_thread.get_time = MagicMock(side_effect=ValueError)
    obs_thread.set_time = MagicMock()
    obs_thread.remaining_time = 60
    OBSThread.pause = False

    obs_thread.update_time(10)

    obs_thread.get_time.assert_called_once()
    obs_thread.set_time.assert_not_called()
    assert OBSThread.pause == True