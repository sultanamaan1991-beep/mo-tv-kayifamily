#!/usr/bin/env python3
"""Play several catalog episodes on headless Kodi, verify each starts.

Reads name|url lines from /tmp/playback_tests.txt. For each: Player.Open,
wait, confirm an active video player at speed 1, then stop.
"""

import json
import socket
import sys
import time
import urllib.parse

HOST, PORT = "127.0.0.1", 9090


def rpc(method, params=None, rid=1, timeout=30):
    s = socket.create_connection((HOST, PORT), timeout=timeout)
    s.settimeout(timeout)
    payload = {"jsonrpc": "2.0", "method": method, "id": rid}
    if params is not None:
        payload["params"] = params
    s.sendall((json.dumps(payload) + "\n").encode())
    buf = b""
    while True:
        buf += s.recv(65536)
        for line in buf.split(b"\n"):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == rid:
                s.close()
                if "error" in msg:
                    raise RuntimeError("RPC error: %s" % msg["error"])
                return msg.get("result")


def main():
    tests = [l.strip().split("|", 1) for l in open("/tmp/playback_tests.txt")
             if l.strip()]
    results = []
    for name, url in tests:
        play = ("plugin://plugin.video.kayifamily/?action=play&"
                + urllib.parse.urlencode({"url": url, "title": name}))
        try:
            rpc("Player.Open", {"item": {"file": play}}, 1)
            time.sleep(50)  # resolve + HLS startup
            players = rpc("Player.GetActivePlayers", rid=2) or []
            props = rpc("Player.GetProperties",
                        {"playerid": 1, "properties": ["time", "speed"]}, 3)
            t = props["time"]
            playing = (len(players) > 0 and props["speed"] == 1
                       and (t["minutes"] * 60 + t["seconds"]) > 0)
            detail = "%02d:%02d:%02d speed=%s" % (
                t["hours"], t["minutes"], t["seconds"], props["speed"])
        except Exception as exc:
            playing, detail = False, "EXC %r" % exc
        try:
            rpc("Player.Stop", {"playerid": 1}, 4)
        except Exception:
            pass
        time.sleep(3)
        results.append((name, playing, detail))
        print(("PASS " if playing else "FAIL ") + name + " | " + detail,
              flush=True)
    print("OVERALL:", "PASS" if all(r[1] for r in results) else "FAIL")
    sys.exit(0 if all(r[1] for r in results) else 1)


if __name__ == "__main__":
    main()
