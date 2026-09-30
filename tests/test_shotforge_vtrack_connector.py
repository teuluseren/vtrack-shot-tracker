import asyncio
import contextlib
import json
from pathlib import Path
import socket
import tempfile
import unittest

from shotforge_vtrack_connector.bridge import Bridge, DEFAULTS, JsonStream, load_config, normalize_shot


class ProtocolTests(unittest.TestCase):
    def test_vtrack_ball_packet_is_not_a_heartbeat_and_measurements_are_preserved(self):
        source = {"APIVersion": "1", "BallData": {"Speed": 98.25, "VLA": 17.0,
                  "HLA": -2.5, "TotalSpin": 4300.0}, "ClubData": {"Speed": 78.5},
                  "ShotDataOptions": {"ContainsBallData": True, "ContainsClubData": True,
                  "IsHeartBeat": True, "LaunchMonitorIsReady": True}}
        target = normalize_shot(source)
        self.assertFalse(target["ShotDataOptions"]["IsHeartBeat"])
        self.assertTrue(source["ShotDataOptions"]["IsHeartBeat"])
        self.assertEqual(target["BallData"], source["BallData"])
        self.assertEqual(target["ClubData"], source["ClubData"])
        self.assertEqual(target["APIversion"], "1")
        self.assertEqual(target["APIVersion"], "1")

    def test_status_or_invalid_ball_packet_does_not_become_a_shot(self):
        for ball in (None, {}, {"Speed": 0}, {"Speed": -1}, {"Speed": True}, {"Speed": "20"}):
            source = {"BallData": ball, "ShotDataOptions": {"ContainsBallData": True, "IsHeartBeat": True}}
            self.assertEqual(normalize_shot(source), source)
        state = {"ShotDataOptions": {"ContainsBallData": False, "IsHeartBeat": True}}
        self.assertEqual(normalize_shot(state), state)

    def test_fragmented_utf8_and_mixed_framing(self):
        objects = [{"Player": {"Club": "café"}}, {"Code": 200}, {"Code": 201}]
        raw = b" \0" + json.dumps(objects[0], ensure_ascii=False).encode() + b"\0\r\n" + json.dumps(objects[1]).encode() + json.dumps(objects[2]).encode()
        parser = JsonStream()
        received = []
        for byte in raw:
            received.extend(parser.feed(bytes([byte])))
        parser.finish()
        self.assertEqual(received, objects)

    def test_invalid_oversized_and_truncated_data(self):
        for data in (b"garbage", b'{broken}\0', b"\xff"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                JsonStream().feed(data)
        with self.assertRaises(ValueError):
            JsonStream(limit=8).feed(b'{"long":"value"}')
        parser = JsonStream()
        parser.feed(b'{"Code":')
        with self.assertRaises(ValueError):
            parser.finish()

    def test_rejects_self_proxy_and_nonlocal_listener(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            for config in ({"listen_port": 921}, {"listen_host": "0.0.0.0"}, {"reply_mode": "fake"}, {"listen_port": True}):
                path.write_text(json.dumps(config), encoding="utf-8-sig")
                with self.subTest(config=config), self.assertRaises(ValueError):
                    load_config(path)
            path.write_text("{}", encoding="utf-8-sig")
            self.assertEqual(load_config(path), DEFAULTS)


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.peers = asyncio.Queue()
        self.writers = []

        async def accepted(reader, writer):
            self.writers.append(writer)
            await self.peers.put((reader, writer))

        self.sf = await asyncio.start_server(accepted, "127.0.0.1", 0)
        config = dict(DEFAULTS, shotforge_port=self.sf.sockets[0].getsockname()[1])
        self.bridge = Bridge(config)
        self.listener = await asyncio.start_server(self.bridge.handle, "127.0.0.1", 0)
        self.port = self.listener.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.listener.close()
        self.sf.close()
        for writer in self.writers:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
        for task in list(self.bridge.sessions):
            task.cancel()
        await asyncio.gather(*list(self.bridge.sessions), return_exceptions=True)
        await self.listener.wait_closed()
        await self.sf.wait_closed()

    async def connect(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.writers.append(writer)
        return reader, writer

    async def next_peer(self):
        return await asyncio.wait_for(self.peers.get(), 2)

    async def reply(self, reader):
        return json.loads((await asyncio.wait_for(reader.readuntil(b"\0"), 2))[:-1])

    async def test_shot_bytes_preserved_and_ack_requires_shotforge(self):
        self.bridge.config["shot_mode"] = "passthrough"
        client, writer = await self.connect()
        sf_reader, sf_writer = await self.next_peer()
        raw = b'{ "APIVersion": "1", "ShotNumber": 42, "BallData":{"Speed":112.25}, "ShotDataOptions":{"ContainsBallData":true}}\0'
        writer.write(raw[:15])
        await writer.drain()
        writer.write(raw[15:])
        await writer.drain()
        self.assertEqual(await asyncio.wait_for(sf_reader.readexactly(len(raw)), 2), raw)
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(client.read(1), .05)
        sf_writer.write(b'{"Code":200,"Message":"Accepted","Extension":12}\0')
        await sf_writer.drain()
        self.assertEqual(await self.reply(client), {"Code": 200, "Message": "Shot received", "Extension": 12})
        self.assertEqual(self.bridge.status["shots_forwarded"], 1)

    async def test_default_relay_corrects_fragmented_ball_frame_heartbeat(self):
        _, writer = await self.connect()
        sf_reader, _ = await self.next_peer()
        source = {"APIVersion": "1", "Units": "Yards", "BallData": {"Speed": 98.5, "VLA": 15.0},
                  "ShotDataOptions": {"ContainsBallData": True, "IsHeartBeat": True}}
        raw = json.dumps(source).encode() + b"\0"
        writer.write(raw[:40])
        await writer.drain()
        writer.write(raw[40:])
        await writer.drain()
        forwarded = await self.reply(sf_reader)
        self.assertFalse(forwarded["ShotDataOptions"]["IsHeartBeat"])
        self.assertEqual(forwarded["BallData"], source["BallData"])
        self.assertEqual(forwarded["APIversion"], "1")
        self.assertEqual(self.bridge.status["shots_forwarded"], 1)

    async def test_unsolicited_player_and_error_preserved(self):
        client, _ = await self.connect()
        _, sf_writer = await self.next_peer()
        player = {"Handed": "LH", "Club": "PT", "DistanceToTarget": 12.5, "Surface": "Green"}
        sf_writer.write(json.dumps({"Code": 201, "Message": "Player Information", "Player": player}).encode())
        await sf_writer.drain()
        response = await self.reply(client)
        self.assertEqual(response["Player"], player)
        self.assertEqual(response["Message"], "GSPro Player Information")
        error = {"Code": 501, "Message": "Shot rejected", "Detail": "test"}
        sf_writer.write(json.dumps(error).encode() + b"\0")
        await sf_writer.drain()
        self.assertEqual(await self.reply(client), error)

    async def test_passthrough_keeps_response_bytes(self):
        self.bridge.config["reply_mode"] = "passthrough"
        client, _ = await self.connect()
        _, sf_writer = await self.next_peer()
        raw = b'{ "Code":201, "Player": {"Club":"PT"}}\n\0'
        sf_writer.write(raw)
        await sf_writer.drain()
        self.assertEqual(await asyncio.wait_for(client.readexactly(len(raw)), 2), raw)

    async def test_disconnect_closes_client_and_allows_reconnect(self):
        client, _ = await self.connect()
        _, sf_writer = await self.next_peer()
        sf_writer.close()
        await sf_writer.wait_closed()
        self.assertEqual(await asyncio.wait_for(client.read(), 2), b"")
        for _ in range(100):
            if not self.bridge.active:
                break
            await asyncio.sleep(.01)
        second, writer = await self.connect()
        sf_reader, _ = await self.next_peer()
        writer.write(b'{"ShotNumber":2}\0')
        await writer.drain()
        self.assertEqual(await asyncio.wait_for(sf_reader.readuntil(b"\0"), 2), b'{"ShotNumber":2}\0')

    async def test_unavailable_target_no_false_success(self):
        self.bridge.config["connect_timeout"] = .1
        self.sf.close()
        await self.sf.wait_closed()
        client, _ = await self.connect()
        self.assertEqual(await asyncio.wait_for(client.read(), 2), b"")
        self.assertEqual(self.bridge.status["responses_received"], 0)
        self.assertTrue(self.bridge.status["last_error"])

    async def test_second_client_rejected_without_disturbing_first(self):
        client, writer = await self.connect()
        sf_reader, _ = await self.next_peer()
        extra, _ = await self.connect()
        self.assertEqual(await asyncio.wait_for(extra.read(), 2), b"")
        writer.write(b"{}\0")
        await writer.drain()
        self.assertEqual(await asyncio.wait_for(sf_reader.readexactly(3), 2), b"{}\0")
        self.assertTrue(self.bridge.active)

    async def test_port_conflict_does_not_claim_readiness(self):
        config = dict(DEFAULTS, listen_port=self.port)
        other = Bridge(config)
        with self.assertRaises(OSError):
            await other.serve(asyncio.Event())
        self.assertFalse(other.status["listening"])
        self.assertIn("Cannot listen", other.status["last_error"])


if __name__ == "__main__":
    unittest.main()
