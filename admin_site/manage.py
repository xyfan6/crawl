#!/usr/bin/env python
"""Django management entry point for the admin site."""
import os
import sys
from pathlib import Path


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin_site.settings")

    # Load .env from the repo root (one level above this file)
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and the "
            "virtualenv is active."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
