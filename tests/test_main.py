from unittest.mock import patch
import main

@patch('twitch.setup_twitch_listener')
def test_main(mock_setup_twitch_listener):
    main.main([])
    mock_setup_twitch_listener.assert_awaited_once()


@patch('twitch.setup_twitch_listener')
def test_check_config_does_not_connect(mock_setup_twitch_listener, capsys):
    main.main(['--check-config'])
    mock_setup_twitch_listener.assert_not_called()
    assert 'Configuration and dependencies loaded:' in capsys.readouterr().out
