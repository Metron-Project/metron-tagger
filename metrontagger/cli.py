"""Cli for Metron-Tagger."""

from argparse import Namespace
from logging import getLogger

import questionary

from metrontagger import __version__, init_logging
from metrontagger.options import check_args, make_parser
from metrontagger.run import Runner
from metrontagger.settings import MetronTaggerSettings
from metrontagger.ui import UIPresenter

LOGGER = getLogger(__name__)


def get_args() -> Namespace:
    """Parse command line arguments.

    This function parses the command line arguments using the configured argument parser and returns the parsed
    arguments.

    Returns:
        Namespace: The parsed command line arguments.
    """

    parser = make_parser()
    args = parser.parse_args()
    check_args(parser, args)
    return args


def _ask(question: str) -> str:
    """Ask the user for text, exiting if they cancel the prompt.

    questionary's `ask()` returns None when the user presses Ctrl-C (after printing
    "Cancelled by user"), so that's treated as a request to quit rather than an answer.

    Returns:
        The answer with surrounding whitespace removed; may be empty.
    """
    answer = questionary.text(question).ask()
    if answer is None:
        raise SystemExit(1)
    return answer.strip()


def _metron_credentials(settings: MetronTaggerSettings) -> None:
    """Prompt for and store a Metron API token if one isn't already configured.

    Exits if no token is given, since online tagging can't work without one.
    """
    if settings.get_str("metron.auth_token"):
        return

    UIPresenter.print_info(
        "Metron-Tagger authenticates with a Metron API token. You can generate one "
        "from your Metron profile page under 'API Tokens'."
    )
    if not (token := _ask("What is your Metron API token?")):
        UIPresenter.print_error("A Metron API token is needed for --online and --id. Exiting.")
        raise SystemExit(1)
    settings["metron.auth_token"] = token
    LOGGER.debug("Added Metron API token")


def _set_sort_directory(settings: MetronTaggerSettings) -> None:
    """Prompt for the default sort directory if not set, and store it.

    An empty answer isn't stored; sorting then reports that no directory was given.
    """
    if settings.get_str("sort.directory"):
        return

    if sort_dir := _ask("What is the default sort directory?"):
        settings["sort.directory"] = sort_dir
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
