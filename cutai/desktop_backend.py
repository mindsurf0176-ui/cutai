"""Dedicated desktop backend entrypoint for packaged Tauri builds."""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CutAI desktop backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18910)
    args = parser.parse_args()

    uvicorn.run("cutai.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
