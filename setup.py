#!/usr/bin/env python3
"""Legacy setup.py shim for CAT (Coding Agent Terminal).

The primary packaging configuration lives in ``pyproject.toml``
(setuptools backend). This file exists for older tools that still
invoke ``setup.py`` directly; it delegates everything to setuptools,
which reads ``pyproject.toml``.
"""

from setuptools import setup

if __name__ == "__main__":
    setup()
