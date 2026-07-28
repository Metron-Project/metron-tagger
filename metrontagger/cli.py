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


def _prompt_for_token(settings: MetronTaggerSettings) -> None:
    """Prompt for and store a Metron API token."""
    settings["metron.auth_token"] = questionary.text("What is your Metron API token?").ask()
    LOGGER.debug("Added Metron API token")


def _prompt_for_username_password(settings: MetronTaggerSettings) -> None:
    """Prompt for Metron username/password if not already set."""
    if not settings["metron.user"]:
        settings["metron.user"] = questionary.text("What is your Metron username?").ask()
        LOGGER.debug("Added Metron username")
    if not settings["metron.password"]:
        settings["metron.password"] = questionary.text("What is your Metron password?").ask()
        LOGGER.debug("Added Metron password")


def _offer_token_migration(settings: MetronTaggerSettings) -> None:
    """Offer existing username/password users a one-time switch to an API token.

    Metron now supports revocable API tokens as an alternative to Basic Auth.
    Existing users are asked once whether they'd like to migrate; if they
    decline, they're not asked again on subsequent runs.
    """
    if settings["metron.token_migration_prompted"]:
        return

    settings["metron.token_migration_prompted"] = True

    questionary.print(
        "Metron now supports API tokens as an alternative to your username and "
        "password. Tokens are revocable and don't require storing your account "
        "password. You can generate one from your Metron profile page under "
        "'API Tokens'.",
        style=Styles.INFO,
    )
    if not questionary.confirm(
        "Would you like to switch to token-based authentication now?", default=False
    ).ask():
        return

    _prompt_for_token(settings)
    if settings["metron.auth_token"]:
        settings.remove_option("metron.user")
        settings.remove_option("metron.password")
        LOGGER.info("Migrated Metron credentials to API token authentication")


def _metron_credentials(settings: MetronTaggerSettings) -> None:
    """Ensure Metron credentials are configured, prompting the user if needed.

    Preference order: an existing API token is used as-is. Existing
    username/password users are offered a one-time migration to a token. If
    neither is configured, the user is asked to choose between the two
    authentication methods.
    """
    if settings["metron.auth_token"]:
        return

    if settings["metron.user"] and settings["metron.password"]:
        _offer_token_migration(settings)
        return

    if questionary.confirm(
        "Authenticate with a Metron API token instead of a username and password? (Recommended)",
        default=True,
    ).ask():
        _prompt_for_token(settings)
    else:
        _prompt_for_username_password(settings)


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
