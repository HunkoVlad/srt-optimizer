"""Compatibility wrapper for the Airbnb search-screening diagnostic."""

from __future__ import annotations

import sys

from airbnb.airbnb_search_screening import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
