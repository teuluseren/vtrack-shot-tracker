import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from vtrack_updater import SemVer, UpdateError, check_for_update, download_update


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class FakeOpener:
    def __init__(self, responses):
        self.responses = responses

    def __call__(self, request, timeout=0):
        url = request.full_url
        if url not in self.responses:
            raise OSError(f"Unexpected URL: {url}")
        return FakeResponse(self.responses[url])


def release_payload(installer=b"verified installer"):
    version = "0.2.0"
    setup_name = f"VTrackShotTracker-Setup-{version}.exe"
    sums_name = f"VTrackShotTracker-{version}-SHA256SUMS.txt"
    digest = hashlib.sha256(installer).hexdigest()
    base = f"https://github.com/teuluseren/vtrack-shot-tracker/releases/download/v{version}"
    return {
        "tag_name": f"v{version}",
        "name": "VTrack 0.2.0",
        "body": "Safe updater release.",
        "html_url": f"https://github.com/teuluseren/vtrack-shot-tracker/releases/tag/v{version}",
        "published_at": "2026-08-30T12:00:00Z",
        "assets": [
            {
                "name": setup_name,
                "browser_download_url": f"{base}/{setup_name}",
                "size": len(installer),
                "digest": f"sha256:{digest}",
            },
            {
                "name": sums_name,
                "browser_download_url": f"{base}/{sums_name}",
                "size": 100,
            },
        ],
    }


class UpdaterTests(unittest.TestCase):
    def test_semver_precedence(self):
        ordered = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
            "1.1.0",
        ]
        parsed = [SemVer.parse(value) for value in ordered]
        self.assertEqual(sorted(parsed), parsed)
        with self.assertRaises(ValueError):
            SemVer.parse("1.0.0-beta.01")

    def test_check_requires_exact_versioned_release_assets(self):
        payload = release_payload()
        opener = FakeOpener(
            {
                "https://api.github.com/repos/teuluseren/vtrack-shot-tracker/releases/latest": json.dumps(payload).encode()
            }
        )
        result = check_for_update("0.1.2", opener=opener)
        self.assertTrue(result["update_available"])
        self.assertEqual(result["latest_version"], "0.2.0")
        self.assertEqual(result["setup"]["name"], "VTrackShotTracker-Setup-0.2.0.exe")

        payload["assets"][0]["name"] = "some-other-installer.exe"
        opener = FakeOpener(
            {
                "https://api.github.com/repos/teuluseren/vtrack-shot-tracker/releases/latest": json.dumps(payload).encode()
            }
        )
        with self.assertRaises(UpdateError):
            check_for_update("0.1.2", opener=opener)

    def test_download_verifies_checksum_and_github_digest(self):
        installer = b"authentic setup bytes"
        payload = release_payload(installer)
        release_api = FakeOpener(
            {
                "https://api.github.com/repos/teuluseren/vtrack-shot-tracker/releases/latest": json.dumps(payload).encode()
            }
        )
        release = check_for_update("0.1.2", opener=release_api)
        expected = hashlib.sha256(installer).hexdigest()
        checksum = f"{expected}  {release['setup']['name']}\n".encode()
        downloads = FakeOpener(
            {
                release["checksums"]["url"]: checksum,
                release["setup"]["url"]: installer,
            }
        )
        with tempfile.TemporaryDirectory() as tempdir:
            path = download_update(release, Path(tempdir), opener=downloads)
            self.assertEqual(path.read_bytes(), installer)
            self.assertEqual(path.name, "VTrackShotTracker-Setup-0.2.0.exe")

    def test_download_rejects_checksum_mismatch(self):
        installer = b"tampered setup bytes"
        payload = release_payload(installer)
        release_api = FakeOpener(
            {
                "https://api.github.com/repos/teuluseren/vtrack-shot-tracker/releases/latest": json.dumps(payload).encode()
            }
        )
        release = check_for_update("0.1.2", opener=release_api)
        release["setup"]["digest"] = "sha256:" + ("0" * 64)
        checksum = f"{'1' * 64}  {release['setup']['name']}\n".encode()
        downloads = FakeOpener({release["checksums"]["url"]: checksum})
        with tempfile.TemporaryDirectory() as tempdir, self.assertRaises(UpdateError):
            download_update(release, Path(tempdir), opener=downloads)


if __name__ == "__main__":
    unittest.main()
