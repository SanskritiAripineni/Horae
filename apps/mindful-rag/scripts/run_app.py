"""Compatibility wrapper around `mindful-rag run-app`."""

import sys

from _bootstrap import bootstrap_local_src

bootstrap_local_src()

from mindful_rag.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["run-app", *sys.argv[1:]]))
