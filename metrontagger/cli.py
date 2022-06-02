"""Cli for Metron-Tagger."""

from argparse import Namespace

from metrontagger.options import make_parser
from metrontagger.run import Runner
from metrontagger.settings import MetronTaggerSettings


def get_args() -> Namespace:
    parser = make_parser()
    return parser.parse_args()


def get_configs(opts: Namespace) -> MetronTaggerSettings:
    config = MetronTaggerSettings()
    if opts.user:
        config.metron_user = opts.user

    if opts.password:
        config.metron_pass = opts.password

    if opts.path:
        config.path = opts.path

    if opts.sort_dir:
        config.sort_dir = opts.sort_dir

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

    if opts.export_to_cb7:
        config.export_to_cb7 = opts.export_to_cb7

    if opts.set_metron_user or opts.set_sort_dir:
        config.save()

    return config


def main():
    args = get_args()
    config = get_configs(args)

    runner = Runner(config)
    runner.run()


if __name__ == "__main__":
    main()
