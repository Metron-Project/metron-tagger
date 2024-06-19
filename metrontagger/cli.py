"""Cli for Metron-Tagger."""

from argparse import Namespace

from metrontagger.options import make_parser
from metrontagger.run import Runner
from metrontagger.settings import MetronTaggerSettings


def get_args() -> Namespace:
    """Parse command line arguments.

    This function parses the command line arguments using the configured argument parser and returns the parsed
    arguments.

    Returns:
        Namespace: The parsed command line arguments.
    """

    parser = make_parser()
    return parser.parse_args()


def get_configs(opts: Namespace) -> MetronTaggerSettings:  # noqa: PLR0912
    """Get MetronTaggerSettings from command line options.

    This function creates a MetronTaggerSettings object based on the provided command line options.

    Args:
        opts (Namespace): The parsed command line options.

    Returns:
        MetronTaggerSettings: The MetronTaggerSettings object with configurations based on the command line options.
    """

    config = MetronTaggerSettings()
    if opts.path:
        config.path = opts.path

    if opts.id:
        config.id = opts.id

    if opts.online:
        config.online = opts.online

    if opts.missing:
        config.missing = opts.missing

    if opts.delete:
        config.delete = opts.delete

    if opts.rename:
        config.rename = opts.rename

    if opts.sort:
        config.sort = opts.sort

    if opts.interactive:
        config.interactive = opts.interactive

    if opts.ignore_existing:
        config.ignore_existing = opts.ignore_existing

    if opts.export_to_cbz:
        config.export_to_cbz = opts.export_to_cbz

    if opts.delete_original:
        config.delete_original = opts.delete_original

    if opts.validate:
        config.validate = opts.validate

    if opts.remove_non_valid:
        config.remove_non_valid = opts.remove_non_valid

    if opts.duplicates:
        config.duplicates = opts.duplicates

    return config


def main() -> None:
    """Execute the Metron Tagger application.

    This function parses command line arguments, creates MetronTaggerSettings based on the arguments, initializes a
    Runner with the settings, and runs the main operations of the application.

    Returns:
        None
    """

    args = get_args()
    config = get_configs(args)

    runner = Runner(config)
    runner.run()


if __name__ == "__main__":
    main()
