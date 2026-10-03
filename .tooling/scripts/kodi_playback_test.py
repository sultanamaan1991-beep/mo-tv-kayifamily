#!/usr/bin/env python3
"""Drive the headless Kodi over TCP JSON-RPC (port 9090) for the playback test.

1. Player.Open the add-on's real play URL (exercises main.py play() +
   the live resolver + inputstream.adaptive handoff).
2. Poll player state; verify time advances over ~3 minutes.
3. Exercise pause/resume and seek.
4. Report PASS/FAIL.
"""

import json
import socket
import sys
import time
import urllib.parse

HOST, PORT = "127.0.0.1", 9090
EPISODE_URL = "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/"
PLAY_URL = (
    "plugin://plugin.video.kayifamily/?action=play&"
    + urllib.parse.urlencode({"url": EPISODE_URL, "title": "MFS85 Test"})
)

_req_id = [0]


def rpc(sock, method, params=None):
    _req_id[0] += 1
    payload = {"jsonrpc": "2.0", "method": method, "id": _req_id[0]}
    if params is not None:
        payload["params"] = params
    sock.sendall((json.dumps(payload) + "\n").encode())
    buf = b""
    deadline = time.time() + 20
    while time.time() < deadline:
        chunk = sock.recv(65536)
        if not chunk:
            raise RuntimeError("socket closed")
        buf += chunk
        for line in buf.split(b"\n"):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == _req_id[0]:
                if "error" in msg:
                    raise RuntimeError("RPC error: %s" % msg["error"])
                return msg.get("result")
    raise RuntimeError("RPC timeout for %s" % method)


def fmt_time(t):
    return "%02d:%02d:%02d" % (t["hours"], t["minutes"], t["seconds"])


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    sock = socket.create_connection((HOST, PORT), timeout=15)
    print("RPC: connected, ping ->", rpc(sock, "JSONRPC.Ping"))

    print("RPC: Player.Open %s..." % PLAY_URL[:80])
    rpc(sock, "Player.Open", {"item": {"file": PLAY_URL}})

    # Wait for the video player to become active (resolver + ISA startup).
    player_id = None
    for _ in range(60):
        players = rpc(sock, "Player.GetActivePlayers") or []
        video = [p for p in players if p.get("type") == "video"]
        if video:
            player_id = video[0]["playerid"]
            break
        time.sleep(2)
    if player_id is None:
        print("FAIL: no video player became active within 120s")
        sys.exit(1)
    print("PASS: video player active (playerid=%s)" % player_id)

    props = lambda: rpc(
        sock, "Player.GetProperties",
        {"playerid": player_id,
         "properties": ["time", "duration", "speed", "percentage", "type"]},
    )

    # Watch time advance.
    start = time.time()
    samples = []
    paused_tested = False
    seek_tested = False
    while time.time() - start < minutes * 60:
        p = props()
        t = p["time"]
        secs = t["hours"] * 3600 + t["minutes"] * 60 + t["seconds"]
        samples.append(secs)
        print("  t=%s speed=%s pct=%.1f%%" % (
            fmt_time(t), p["speed"], p["percentage"]))
        elapsed = time.time() - start
        if not paused_tested and elapsed > 45:
            rpc(sock, "Player.PlayPause", {"playerid": player_id})
            time.sleep(3)
            p2 = props()
            rpc(sock, "Player.PlayPause", {"playerid": player_id})
            print("  pause/resume: speed went %s -> %s -> %s" % (
                p["speed"], p2["speed"], props()["speed"]))
            paused_tested = True
        if not seek_tested and elapsed > 90:
            rpc(sock, "Player.Seek",
                {"playerid": player_id, "value": {"seconds": 1200}})
            time.sleep(5)
            print("  seek to 20:00 -> now at %s" % fmt_time(props()["time"]))
            seek_tested = True
        time.sleep(20)

    if len(set(samples)) < 3:
        print("FAIL: playback time did not advance (samples=%s)" % samples[:6])
        sys.exit(1)
    span = max(samples) - min(samples)
    print("PASS: time advanced %d seconds over %.1f wall minutes "
          "(pause/resume=%s, seek=%s)" % (
              span, minutes, paused_tested, seek_tested))
    rpc(sock, "Player.Stop", {"playerid": player_id})
    print("DONE")


if __name__ == "__main__":
    main()
