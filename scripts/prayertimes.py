#!/usr/bin/env python3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
LIB_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "prayertimes")
if os.path.isdir(LIB_DIR):
    sys.path.insert(0, os.path.dirname(LIB_DIR))

from prayertimes.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
