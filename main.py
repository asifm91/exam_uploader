import argparse

import admin_page
import submission_page


from nicegui import ui


def parse_args():
    parser = argparse.ArgumentParser(description="Exam Uploader server")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode (hot-reload on file changes, auto-open browser). "
        "Do NOT use this during a live exam in the lab.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    return parser.parse_args()


if __name__ in {"__main__", "__mp_main__"}:
    args = parse_args()
    mode = "dev" if args.dev else "lab"
    print(f"Running in {mode} mode on {args.host}:{args.port}")

    ui.run(
        storage_secret="some random secret that is really hard to guess",
        host=args.host,
        port=args.port,
        reload=args.dev,
        show=False,
        reconnect_timeout=3.0 if args.dev else 60.0,
    )
