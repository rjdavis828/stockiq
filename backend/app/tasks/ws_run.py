"""Standalone entrypoint for the Finnhub WS worker.

Run as a dedicated container process:
    python -m app.tasks.ws_run
"""
import asyncio
import logging

from app.tasks.ws_finnhub import _ws_loop


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    asyncio.run(_ws_loop())


if __name__ == "__main__":
    main()
