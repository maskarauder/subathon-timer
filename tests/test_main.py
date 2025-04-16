import pytest
from unittest.mock import patch
import main

@patch('main.setup_twitch_listener')
def test_main(mock_setup_twitch_listener):
    main.main()
    mock_setup_twitch_listener.assert_called_once()