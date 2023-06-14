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

    if opts.export_to_cb7:
        config.export_to_cb7 = opts.export_to_cb7

    if opts.export_to_cbz:
        config.export_to_cbz = opts.export_to_cbz

    if opts.delete_original:
        config.delete_original = opts.delete_original

    if opts.v2:
        config.comic_info_v2 = opts.v2

    if opts.v1:
        config.comic_info_v1 = opts.v1

    return config


def main():
    args = get_args()
    config = get_configs(args)

    runner = Runner(config)
    runner.run()


if __name__ == "__main__":
    main()
