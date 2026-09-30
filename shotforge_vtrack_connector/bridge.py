"""Relay VTrack Open Connect traffic to ShotForge using only the standard library.

VTrack measurements are preserved while its shot envelope is adapted for
ShotForge. Success is never invented before ShotForge responds.
"""
from __future__ import annotations

import argparse
import asyncio
import codecs
import contextlib
import json
import logging
import math
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time

LOG = logging.getLogger("shotforge_vtrack")
DEFAULTS = {
    "listen_host": "127.0.0.1", "listen_port": 12485,
    "shotforge_host": "127.0.0.1", "shotforge_port": 921,
    "reply_mode": "gspro", "reply_delimiter": "nul", "connect_timeout": 5.0,
    "shot_mode": "vtrack",
}


def load_config(path: Path) -> dict:
    config = dict(DEFAULTS)
    config.update(json.loads(path.read_text(encoding="utf-8-sig")))
    if config["listen_host"] != "127.0.0.1":
        raise ValueError("listen_host must be 127.0.0.1 (local VTrack only)")
    for key in ("listen_port", "shotforge_port"):
        if type(config[key]) is not int or not 1 <= config[key] <= 65535:
            raise ValueError(f"{key} must be a port from 1 to 65535")
    if not isinstance(config["shotforge_host"], str) or not config["shotforge_host"].strip():
        raise ValueError("shotforge_host must be a host name or IP address")
    if (config["shotforge_host"].lower() in ("127.0.0.1", "localhost", "::1")
            and config["listen_port"] == config["shotforge_port"]):
        raise ValueError("VTrack and ShotForge must use different ports")
    if config["reply_mode"] not in ("gspro", "passthrough"):
        raise ValueError("reply_mode must be gspro or passthrough")
    if config["shot_mode"] not in ("vtrack", "passthrough"):
        raise ValueError("shot_mode must be vtrack or passthrough")
    if config["reply_delimiter"] not in ("nul", "newline", "none"):
        raise ValueError("reply_delimiter must be nul, newline or none")
    if not isinstance(config["connect_timeout"], (int, float)) or not 0 < config["connect_timeout"] <= 60:
        raise ValueError("connect_timeout must be greater than 0 and at most 60 seconds")
    return config


class JsonStream:
    """Bounded incremental UTF-8 parser for concatenated, newline or NUL JSON."""
    def __init__(self, limit: int = 1_048_576):
        self.text = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")()
        self.limit = limit

    def feed(self, data: bytes) -> list[dict]:
        self.text += self.decoder.decode(data)
        if len(self.text) > self.limit:
            raise ValueError("JSON message exceeds buffer limit")
        result = []
        while True:
            self.text = self.text.lstrip(" \r\n\t\x00\ufeff")
            if not self.text:
                return result
            if self.text[0] != "{":
                raise ValueError("Expected a JSON object")
            try:
                obj, end = json.JSONDecoder().raw_decode(self.text)
            except json.JSONDecodeError:
                # A delimiter cannot occur inside valid JSON except escaped.
                if "\x00" in self.text:
                    raise ValueError("Malformed NUL-delimited JSON") from None
                return result
            result.append(obj)
            self.text = self.text[end:]

    def finish(self):
        self.text += self.decoder.decode(b"", final=True)
        if self.text.strip(" \r\n\t\x00\ufeff"):
            raise ValueError("Connection ended with incomplete JSON")


def normalize_reply(obj: dict) -> dict:
    result = dict(obj)
    if obj.get("Code") == 201:
        result["Message"] = "GSPro Player Information"
    elif obj.get("Code") == 200:
        result["Message"] = "Shot received"
    # Preserve player information (including extra fields), errors and extensions.
    return result


def normalize_shot(obj: dict) -> dict:
    """Correct VTrack envelope quirks without changing measured shot values."""
    result = dict(obj)
    if "APIversion" not in result and "APIVersion" in result:
        result["APIversion"] = result["APIVersion"]
    opts = obj.get("ShotDataOptions")
    ball = obj.get("BallData")
    speed = ball.get("Speed") if isinstance(ball, dict) else None
    if (isinstance(opts, dict) and opts.get("ContainsBallData") is True
            and type(speed) in (int, float) and math.isfinite(speed) and speed > 0):
        # VTrack marks actual shots as heartbeats; ShotForge discards those.
        result["ShotDataOptions"] = dict(opts, IsHeartBeat=False)
    return result


def encode_reply(obj: dict, delimiter: str) -> bytes:
    suffix = {"nul": b"\0", "newline": b"\n", "none": b""}[delimiter]
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + suffix


class Bridge:
    def __init__(self, config: dict, status_path: Path | None = None):
        self.config = config
        self.status_path = status_path
        self.active = False
        self.sessions: set[asyncio.Task] = set()
        self.status = {
            "pid": os.getpid(), "parent_pid": os.getppid(), "listening": False, "vtrack_connected": False,
            "shotforge_connected": False, "shots_forwarded": 0,
            "responses_received": 0, "last_error": "",
        }

    def update(self, **changes):
        self.status.update(changes, updated_at=time.time())
        if self.status_path:
            try:
                self.status_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.status_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(self.status), encoding="utf-8")
                temporary.replace(self.status_path)
            except OSError as exc:
                LOG.warning("Cannot write connector status: %s", exc)

    async def from_vtrack(self, reader, writer):
        parser = JsonStream()
        while data := await reader.read(65536):
            objects = parser.feed(data)
            if self.config["shot_mode"] == "passthrough":
                writer.write(data)
            else:
                for obj in objects:
                    writer.write(encode_reply(normalize_shot(obj), "nul"))
            await writer.drain()
            for obj in objects:
                opts = obj.get("ShotDataOptions")
                if isinstance(opts, dict) and opts.get("ContainsBallData") is True:
                    self.update(shots_forwarded=self.status["shots_forwarded"] + 1)
                    ball = obj.get("BallData") or {}
                    LOG.info("Shot forwarded: number=%s speed=%s VLA=%s HLA=%s spin=%s source_heartbeat=%s mode=%s",
                             obj.get("ShotNumber"), ball.get("Speed"), ball.get("VLA"), ball.get("HLA"),
                             ball.get("TotalSpin"), opts.get("IsHeartBeat"), self.config["shot_mode"])
        parser.finish()

    async def from_shotforge(self, reader, writer):
        parser = JsonStream()
        while data := await reader.read(65536):
            objects = parser.feed(data)
            if self.config["reply_mode"] == "passthrough":
                writer.write(data)
            for obj in objects:
                self.update(responses_received=self.status["responses_received"] + 1)
                if obj.get("Code") not in (200, 201):
                    LOG.warning("ShotForge response: code=%s message=%s", obj.get("Code"), obj.get("Message"))
                if self.config["reply_mode"] == "gspro":
                    writer.write(encode_reply(normalize_reply(obj), self.config["reply_delimiter"]))
            await writer.drain()
        parser.finish()

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.sessions.add(task)
        upstream = None
        pumps = []
        owns_session = not self.active
        try:
            if not owns_session:
                LOG.warning("Refusing an additional VTrack connection while a session is active")
                return
            self.active = True
            self.update(vtrack_connected=True, last_error="")
            LOG.info("VTrack connected")
            sf_reader, upstream = await asyncio.wait_for(
                asyncio.open_connection(self.config["shotforge_host"], self.config["shotforge_port"]),
                timeout=self.config["connect_timeout"],
            )
            self.update(shotforge_connected=True)
            LOG.info("ShotForge connected")
            pumps = [asyncio.create_task(self.from_vtrack(reader, upstream)),
                     asyncio.create_task(self.from_shotforge(sf_reader, writer))]
            done, _ = await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
            for completed in done:
                completed.result()
            LOG.info("Peer disconnected; closing both ends so VTrack can reconnect")
        except (OSError, ValueError, TimeoutError) as exc:
            self.update(last_error=str(exc) or type(exc).__name__)
            LOG.warning("Session failed: %s; check ShotForge's Open Connect listener", exc)
        finally:
            for pump in pumps:
                pump.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            for connection in (writer, upstream):
                if connection:
                    connection.close()
                    with contextlib.suppress(OSError, TimeoutError):
                        await asyncio.wait_for(connection.wait_closed(), 2)
            if owns_session:
                self.active = False
                self.update(vtrack_connected=False, shotforge_connected=False)
            self.sessions.discard(task)

    async def serve(self, stop: asyncio.Event):
        try:
            server = await asyncio.start_server(self.handle, self.config["listen_host"], self.config["listen_port"])
        except OSError as exc:
            self.update(last_error=f"Cannot listen on {self.config['listen_port']}: {exc}")
            raise
        self.update(listening=True)
        LOG.info("Listening for VTrack on %s:%s; ShotForge target %s:%s",
                 self.config["listen_host"], self.config["listen_port"],
                 self.config["shotforge_host"], self.config["shotforge_port"])
        try:
            await stop.wait()
        finally:
            server.close()
            for task in list(self.sessions):
                task.cancel()
            await asyncio.gather(*list(self.sessions), return_exceptions=True)
            await server.wait_closed()
            self.update(listening=False)


async def run(args):
    stop = asyncio.Event()
    if args.parent_stdin:
        # A daemon thread avoids asyncio executor shutdown hanging on stdin.
        import threading
        loop = asyncio.get_running_loop()

        def watch_parent():
            sys.stdin.buffer.read(1)
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(stop.set)

        threading.Thread(target=watch_parent, daemon=True).start()
    bridge = Bridge(load_config(args.config), args.status_file)
    await bridge.serve(stop)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("connector.json"))
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--parent-stdin", action="store_true")
    args = parser.parse_args()
    log_dir = args.config.resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[
        logging.StreamHandler(), RotatingFileHandler(log_dir / "bridge.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")])
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as exc:
        LOG.error("Cannot start connector: %s. For a port conflict, close the existing connector or relay first.", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
