"""Secure GitHub Release update support for VTrack Shot Tracker."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable


REPOSITORY = "teuluseren/vtrack-shot-tracker"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
USER_AGENT = "VTrackShotTracker-Updater"
MAX_CHECKSUM_BYTES = 1024 * 1024
MAX_INSTALLER_BYTES = 1024 * 1024 * 1024
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class UpdateError(RuntimeError):
    """Raised when an update cannot be checked, verified, or launched."""


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = SEMVER_RE.fullmatch(value)
        if not match:
            raise ValueError(f"Invalid semantic version: {value}")
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        for identifier in prerelease:
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError(f"Invalid semantic version: {value}")
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease)

    def _compare(self, other: "SemVer") -> int:
        left = (self.major, self.minor, self.patch)
        right = (other.major, other.minor, other.patch)
        if left != right:
            return 1 if left > right else -1
        if not self.prerelease and not other.prerelease:
            return 0
        if not self.prerelease:
            return 1
        if not other.prerelease:
            return -1
        for left_id, right_id in zip(self.prerelease, other.prerelease):
            if left_id == right_id:
                continue
            left_numeric = left_id.isdigit()
            right_numeric = right_id.isdigit()
            if left_numeric and right_numeric:
                return 1 if int(left_id) > int(right_id) else -1
            if left_numeric != right_numeric:
                return -1 if left_numeric else 1
            return 1 if left_id > right_id else -1
        if len(self.prerelease) == len(other.prerelease):
            return 0
        return 1 if len(self.prerelease) > len(other.prerelease) else -1

    def __lt__(self, other: "SemVer") -> bool:
        return self._compare(other) < 0


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )


def _asset(payload: dict, expected_name: str) -> dict:
    assets = payload.get("assets", [])
    if not isinstance(assets, list):
        raise UpdateError("GitHub release metadata has an invalid asset list.")
    for item in assets:
        if isinstance(item, dict) and item.get("name") == expected_name:
            url = str(item.get("browser_download_url") or "")
            parsed = urllib.parse.urlparse(url)
            expected_prefix = f"/{REPOSITORY}/releases/download/"
            if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or not parsed.path.startswith(expected_prefix):
                raise UpdateError(f"Release asset has an unexpected download URL: {expected_name}")
            return item
    raise UpdateError(f"Release is missing required asset: {expected_name}")


def check_for_update(
    current_version: str,
    *,
    opener: Callable[..., BinaryIO] = urllib.request.urlopen,
    timeout: float = 10.0,
) -> dict:
    """Return normalized metadata for GitHub's latest stable release."""
    try:
        current = SemVer.parse(current_version)
    except ValueError as exc:
        raise UpdateError(str(exc)) from exc
    try:
        with opener(_request(LATEST_RELEASE_API), timeout=timeout) as response:
            raw = response.read(MAX_CHECKSUM_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("No published VTrack Shot Tracker release is available yet.") from exc
        raise UpdateError(f"GitHub update check failed (HTTP {exc.code}).") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError(f"Could not reach GitHub to check for updates: {exc}") from exc
    if len(raw) > MAX_CHECKSUM_BYTES:
        raise UpdateError("GitHub returned an unexpectedly large release response.")
    try:
        payload = json.loads(raw.decode("utf-8"))
        tag = str(payload["tag_name"])
        latest_text = tag[1:] if tag.startswith("v") else tag
        latest = SemVer.parse(latest_text)
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise UpdateError("GitHub returned invalid release metadata.") from exc

    setup_name = f"VTrackShotTracker-Setup-{latest_text}.exe"
    checksum_name = f"VTrackShotTracker-{latest_text}-SHA256SUMS.txt"
    setup = _asset(payload, setup_name)
    checksums = _asset(payload, checksum_name)
    try:
        setup_size = int(setup.get("size") or 0)
    except (TypeError, ValueError) as exc:
        raise UpdateError("GitHub release metadata has an invalid installer size.") from exc
    return {
        "current_version": current_version,
        "latest_version": latest_text,
        "update_available": current < latest,
        "release_url": str(payload.get("html_url") or RELEASES_URL),
        "release_name": str(payload.get("name") or tag),
        "release_notes": str(payload.get("body") or ""),
        "published_at": payload.get("published_at"),
        "setup": {
            "name": setup_name,
            "url": str(setup["browser_download_url"]),
            "size": setup_size,
            "digest": str(setup.get("digest") or ""),
        },
        "checksums": {
            "name": checksum_name,
            "url": str(checksums["browser_download_url"]),
        },
    }


def _download_bytes(
    url: str,
    limit: int,
    *,
    opener: Callable[..., BinaryIO],
    timeout: float,
) -> bytes:
    try:
        with opener(_request(url), timeout=timeout) as response:
            data = response.read(limit + 1)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise UpdateError(f"Could not download {Path(urllib.parse.urlparse(url).path).name}: {exc}") from exc
    if len(data) > limit:
        raise UpdateError("Downloaded update metadata exceeded its safety limit.")
    return data


def _expected_checksum(text: str, filename: str) -> str:
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9A-Fa-f]{64})\s+\*?(.+)", line.strip())
        if match and match.group(2) == filename:
            return match.group(1).lower()
    raise UpdateError(f"Checksum file has no SHA-256 entry for {filename}.")


def download_update(
    release: dict,
    destination_root: Path,
    *,
    opener: Callable[..., BinaryIO] = urllib.request.urlopen,
    timeout: float = 30.0,
) -> Path:
    """Download and verify the installer, returning its absolute path."""
    version = str(release.get("latest_version") or "")
    try:
        SemVer.parse(version)
    except ValueError as exc:
        raise UpdateError(str(exc)) from exc
    setup = release.get("setup") or {}
    checksums = release.get("checksums") or {}
    filename = str(setup.get("name") or "")
    if filename != f"VTrackShotTracker-Setup-{version}.exe":
        raise UpdateError("Release installer name does not match its version.")
    try:
        declared_size = int(setup.get("size") or 0)
    except (TypeError, ValueError) as exc:
        raise UpdateError("Release installer size is invalid.") from exc
    if declared_size < 0 or declared_size > MAX_INSTALLER_BYTES:
        raise UpdateError("Release installer size is outside the safety limit.")

    checksum_bytes = _download_bytes(
        str(checksums.get("url") or ""),
        MAX_CHECKSUM_BYTES,
        opener=opener,
        timeout=timeout,
    )
    try:
        expected = _expected_checksum(checksum_bytes.decode("utf-8-sig"), filename)
    except UnicodeDecodeError as exc:
        raise UpdateError("Release checksum file is not valid UTF-8.") from exc
    api_digest = str(setup.get("digest") or "")
    if api_digest and api_digest.lower() != f"sha256:{expected}":
        raise UpdateError("GitHub asset digest does not match the published checksum file.")

    target_dir = Path(destination_root).resolve() / "updates" / version
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    partial = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    total = 0
    try:
        with opener(_request(str(setup.get("url") or "")), timeout=timeout) as response, partial.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_INSTALLER_BYTES:
                    raise UpdateError("Downloaded installer exceeded the safety limit.")
                digest.update(chunk)
                output.write(chunk)
        if declared_size and total != declared_size:
            raise UpdateError(f"Installer size mismatch: expected {declared_size} bytes, received {total}.")
        if digest.hexdigest().lower() != expected:
            raise UpdateError("Installer SHA-256 verification failed; the file was not launched.")
        os.replace(partial, target)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise UpdateError(f"Could not download the update installer: {exc}") from exc
    finally:
        partial.unlink(missing_ok=True)
    return target


def launch_installer(installer: Path) -> None:
    """Launch the verified Inno Setup installer outside the current process group."""
    installer = Path(installer).resolve()
    if os.name != "nt":
        raise UpdateError("The automatic installer is supported only on Windows.")
    if not installer.is_file() or installer.suffix.lower() != ".exe":
        raise UpdateError(f"Verified installer was not found: {installer}")
    try:
        subprocess.Popen(
            [str(installer), "/CLOSEAPPLICATIONS"],
            cwd=str(installer.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
    except OSError as exc:
        raise UpdateError(f"Could not start the update installer: {exc}") from exc
