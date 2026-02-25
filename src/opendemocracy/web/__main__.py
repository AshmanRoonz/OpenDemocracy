"""Launch the OpenDemocracy web server.

Usage:
    python -m opendemocracy.web              # localhost:8000
    python -m opendemocracy.web --port 3000  # custom port
    python -m opendemocracy.web --host 0.0.0.0  # accessible on network
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    """Parse args and start the server."""
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print(
            "Missing web dependencies. Install them with:\n\n"
            "    pip install opendemocracy[web]\n"
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description="OpenDemocracy web server")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    args = parser.parse_args()

    print(f"\n  OpenDemocracy is running at http://{args.host}:{args.port}\n")
    print("  Share this URL — anyone with a browser can participate.")
    print("  Press Ctrl+C to stop.\n")

    uvicorn.run(
        "opendemocracy.web.app:app",
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
