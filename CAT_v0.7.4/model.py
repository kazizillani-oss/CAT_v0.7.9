#!/usr/bin/env python3
"""
CAT v0.7.9.0 — root-level entry shim for source checkouts.

The provider-setup wizard moved into the package (calc_terminal/model.py)
so installed copies of CCT ship it; this shim keeps the documented
`python model.py` workflow working when running from a source tree.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from calc_terminal.model import *  # noqa: F401,F403
from calc_terminal.model import initialize_model , main  # noqa: F401

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Exiting...")
        sys.exit(0)