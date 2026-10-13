"""Cli for Metron-Tagger."""

from argparse import Namespace
from logging import getLogger

import questionary

from metrontagger import __version__, init_logging
from metrontagger.options import make_parser
from metrontagger.run import Runner
from metrontagger.settings import MetronTaggerSettings
from metrontagger.styles import Styles

LOGGER = getLogger(__name__)


def get_args() -> Namespace:
    """Parse command line arguments.

    This function parses the command line arguments using the configured argument parser and returns the parsed
    arguments.

    Returns:
        Namespace: The parsed command line arguments.
    """

    parser = make_parser()
    return parser.parse_args()


def _metron_credentials(settings: MetronTaggerSettings) -> None:
    """Prompt for and store a Metron API token if one isn't already configured."""
    if settings["metron.auth_token"]:
        return

    questionary.print(
        "Metron-Tagger authenticates with a Metron API token. You can generate one "
        "from your Metron profile page under 'API Tokens'.",
        style=Styles.INFO,
    )
    settings["metron.auth_token"] = questionary.text("What is your Metron API token?").ask()
    LOGGER.debug("Added Metron API token")


def _set_sort_directory(settings: MetronTaggerSettings) -> None:
    """Prompt for the default sort directory if not set.

    If the default sort directory is not already set in the settings,
    prompt the user for it and store it.
    """
    if not settings["sort.directory"]:
        settings["sort.directory"] = questionary.text(
            "What is the default sort directory?"
        ).ask()
        LOGGER.debug("Added default sort directory")


def main() -> None:
    """Execute the Metron Tagger application.

    This function parses command line arguments, creates MetronTaggerSettings based on the arguments, initializes a
    Runner with the settings, and runs the main operations of the application.

    Returns:
        None
    """
    init_logging()
    settings = MetronTaggerSettings()
    LOGGER.info("Metron-Tagger v%s", __version__)

    args = get_args()
    if args.online or args.id:
        _metron_credentials(settings=settings)
    if args.sort:
        _set_sort_directory(settings=settings)

    runner = Runner(args, settings)
    runner.run()


if __name__ == "__main__":
    main()
