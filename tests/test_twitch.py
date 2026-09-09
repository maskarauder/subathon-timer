import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import twitch


@pytest.mark.parametrize(
    ("tier", "expected_value"),
    [
        ("1000", twitch.TIER_1_VALUE),
        ("2000", twitch.TIER_2_VALUE),
        ("3000", twitch.TIER_3_VALUE),
    ],
)
def test_new_subscriber_adds_time_for_each_tier(monkeypatch, tier, expected_value):
    obs_thread = MagicMock()
    monkeypatch.setattr(twitch, "obs_thread", obs_thread)
    monkeypatch.setattr(twitch, "RANDOMIZER_ENABLED", False)
    monkeypatch.setattr(twitch, "LOG_ENABLED", False)

    data = SimpleNamespace(
        event=SimpleNamespace(
            tier=tier,
            user_login="subscriber",
            user_name="Subscriber",
            is_gift=False,
        )
    )

    asyncio.run(twitch.callback_new_subscriber(data))

    obs_thread.update_time.assert_called_once_with(expected_value)


def test_resubscriber_logs_the_calculated_value(monkeypatch):
    obs_thread = MagicMock()
    write_to_logfile = AsyncMock()
    monkeypatch.setattr(twitch, "obs_thread", obs_thread)
    monkeypatch.setattr(twitch, "write_to_logfile", write_to_logfile)
    monkeypatch.setattr(twitch, "RANDOMIZER_ENABLED", False)
    monkeypatch.setattr(twitch, "LOG_ENABLED", True)

    data = SimpleNamespace(
        event=SimpleNamespace(
            tier="2000",
            user_login="resubscriber",
            user_name="Resubscriber",
            cumulative_months=12,
            message=SimpleNamespace(text="Another month!"),
        )
    )

    asyncio.run(twitch.callback_resubscriber(data))

    obs_thread.update_time.assert_called_once_with(twitch.TIER_2_VALUE)
    write_to_logfile.assert_awaited_once_with(
        twitch.SUBSCRIPTION_LOGFILE,
        [
            "resubscriber",
            "Resubscriber",
            12,
            2,
            "Another month!",
            twitch.TIER_2_VALUE,
        ],
    )


def test_bits_event_without_message_is_logged(monkeypatch):
    obs_thread = MagicMock()
    write_to_logfile = AsyncMock()
    monkeypatch.setattr(twitch, "obs_thread", obs_thread)
    monkeypatch.setattr(twitch, "write_to_logfile", write_to_logfile)
    monkeypatch.setattr(twitch, "RANDOMIZER_ENABLED", False)
    monkeypatch.setattr(twitch, "LOG_ENABLED", True)

    data = SimpleNamespace(
        event=SimpleNamespace(
            bits=100,
            user_login="powerup_user",
            user_name="PowerUp_User",
            message=None,
        )
    )

    asyncio.run(twitch.callback_bits(data))

    expected_value = int(100 * twitch.BITS_VALUE)
    obs_thread.update_time.assert_called_once_with(expected_value)
    write_to_logfile.assert_awaited_once_with(
        twitch.BITS_LOGFILE,
        ["powerup_user", "PowerUp_User", 100, "", expected_value],
    )


def test_generate_device_tokens(monkeypatch):
    auth = MagicMock()
    auth.get_code = AsyncMock(return_value=("ABCD1234", "https://twitch.example/activate"))
    auth.wait_for_auth_complete = AsyncMock(return_value=("access-token", "refresh-token"))
    code_flow = MagicMock(return_value=auth)
    browser_open = MagicMock()
    monkeypatch.setattr(twitch, "CodeFlow", code_flow)
    monkeypatch.setattr(twitch.webbrowser, "open", browser_open)

    result = asyncio.run(twitch.generate_device_tokens("twitch-client", ["scope"]))

    code_flow.assert_called_once_with("twitch-client", ["scope"])
    auth.get_code.assert_awaited_once_with()
    browser_open.assert_called_once_with("https://twitch.example/activate", new=2)
    auth.wait_for_auth_complete.assert_awaited_once_with()
    assert result == ("access-token", "refresh-token")
