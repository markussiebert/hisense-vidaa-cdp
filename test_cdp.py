#!/usr/bin/env python3
"""Manual smoke test for the Hisense VIDAA CDP client.

Usage:
    python3 test_cdp.py <ip> status|is_on|volup|voldown|mute|unmute
    python3 test_cdp.py <ip> source <0-6>
    python3 test_cdp.py <ip> vol <0-100>
    python3 test_cdp.py <ip> app <name>

Not part of the integration; it only exists to poke a real TV.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

# Make the integration importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aiohttp  # noqa: E402

from custom_components.hisense_vidaa_cdp.cdp import HisenseCDP, TVOffline  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Hisense VIDAA CDP test client")
    parser.add_argument("ip", help="TV IP address")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="print source/volume/mute/channel")
    sub.add_parser("is_on", help="check whether the CDP port answers")
    sub.add_parser("volup", help="press volume up")
    sub.add_parser("voldown", help="press volume down")
    sub.add_parser("mute", help="enable mute")
    sub.add_parser("unmute", help="disable mute")

    source = sub.add_parser("source", help="switch input source")
    source.add_argument("index", type=int, choices=list(range(7)))

    volume = sub.add_parser("vol", help="set volume")
    volume.add_argument("level", type=int, choices=list(range(101)))

    app = sub.add_parser("app", help="start an application")
    app.add_argument("name")

    return parser


async def run(host: str, args: argparse.Namespace) -> Any:
    """Execute the requested operation and return its result."""
    async with aiohttp.ClientSession() as session:
        tv = HisenseCDP(host, session)
        if args.command == "status":
            return await tv.get_status()
        if args.command == "is_on":
            return await tv.is_on()
        if args.command == "volup":
            return await tv.volume_up()
        if args.command == "voldown":
            return await tv.volume_down()
        if args.command == "mute":
            return await tv.set_mute(True)
        if args.command == "unmute":
            return await tv.set_mute(False)
        if args.command == "source":
            return await tv.set_source(args.index)
        if args.command == "vol":
            return await tv.set_volume(args.level)
        if args.command == "app":
            return await tv.start_app(args.name)
        raise ValueError(f"unknown command: {args.command}")


def main() -> int:
    """Parse arguments, run the operation and print the outcome."""
    args = build_parser().parse_args()
    try:
        result = asyncio.run(run(args.ip, args))
    except TVOffline as err:
        print(f"TV offline: {err}")
        return 1
    except Exception as err:  # noqa: BLE001 - CLI should report anything
        print(f"{type(err).__name__}: {err}")
        return 1

    print("ok" if result is None else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
