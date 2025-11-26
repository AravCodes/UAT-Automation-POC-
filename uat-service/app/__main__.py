"""
Make the app package executable via `python -m app`.

This allows running the UAT service with CLI arguments:
    python -m app --concurrency 5 --headless false
    python -m app --legacy
"""

from app.cli import main

if __name__ == "__main__":
    main()
