"""Command-line entry point."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="famulix",
        description="famulix — offline personal-agent framework",
    )
    parser.add_argument("--version", action="store_true", help="print version")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="run a full seeded persona day offline")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from famulix import __version__

        print(__version__)
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    print(f"famulix {args.command}: not yet implemented")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
