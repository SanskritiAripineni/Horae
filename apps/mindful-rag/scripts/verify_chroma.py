"""Compatibility wrapper around `mindful-rag verify-chroma`."""

import sys

from _bootstrap import bootstrap_local_src

bootstrap_local_src()

from mindful_rag.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["verify-chroma", *sys.argv[1:]]))
