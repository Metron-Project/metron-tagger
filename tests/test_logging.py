import logging
from unittest.mock import MagicMock, patch

import pytest

from metrontagger.logging import init_logging
from metrontagger.settings import MetronTaggerSettings

LOG_FMT = "{asctime} - {name} - {levelname} - {message}"
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def test_init_logging_happy_path(tmp_path):
    # Arrange
    config = MagicMock(spec=MetronTaggerSettings)
    config.get_settings_folder.return_value = tmp_path

    # Act
    with patch("logging.FileHandler") as mock_file_handler:
        init_logging(config)

    # Assert
    mock_file_handler.assert_called_once_with(str(tmp_path / "metron-tagger.log"))
    assert logging.getLogger().level == logging.WARNING


@pytest.mark.parametrize(
    ("config", "expected_exception"),
    [
        (None, AttributeError),
        (MagicMock(spec=object), AttributeError),
    ],
    ids=["none_config", "invalid_config"],
)
def test_init_logging_error_cases(config, expected_exception):
    # Act
    with pytest.raises(expected_exception):
        init_logging(config)
