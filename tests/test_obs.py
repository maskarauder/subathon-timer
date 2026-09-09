from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from obs import OBSThread


def connected_obs_thread(text="0:01:00"):
    obs_thread = OBSThread()
    obs_thread.cl = MagicMock()
    obs_thread.inputobj = {"inputName": "subathon_clock"}
    obs_thread.cl.get_input_settings.return_value = SimpleNamespace(
        input_settings={"text": text}
    )
    return obs_thread


def test_update_time_success():
    obs_thread = connected_obs_thread()

    obs_thread.update_time(10)

    obs_thread.cl.set_input_settings.assert_called_once_with(
        "subathon_clock",
        {"text": "0:01:10"},
        True,
    )


def test_update_time_value_error_pauses_timer():
    obs_thread = connected_obs_thread()
    OBSThread.pause = False

    try:
        with patch("obs.fuzzy_strtime_to_int", side_effect=ValueError):
            obs_thread.update_time(10)

        obs_thread.cl.set_input_settings.assert_not_called()
        assert OBSThread.pause is True
    finally:
        OBSThread.pause = False


def test_run_retries_obs_connection():
    obs_thread = OBSThread()
    obs_thread.connect_to_obs = MagicMock(side_effect=[False, True])
    obs_thread.ecl = MagicMock()
    obs_thread.get_time = MagicMock(return_value=0)
    obs_thread.set_time = MagicMock()

    with patch("obs.sleep") as sleep:
        obs_thread.run()

    assert obs_thread.connect_to_obs.call_count == 2
    sleep.assert_called_once_with(1)
    obs_thread.ecl.callback.register.assert_called_once()
    obs_thread.set_time.assert_called_once_with(0)
