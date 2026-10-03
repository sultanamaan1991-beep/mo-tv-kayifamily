#!/usr/bin/env python3
"""Kodi identity verification for issue #3 (robust version).

For each episode in /tmp/identity_kodi_test.txt (name|url|expected_embed):
plays it in Kodi, waits up to 90s for playback, then checks the Kodi log
to confirm the resolver selected the EXPECTED OK.ru embed ID.
"""

import json
import re
import socket
import sys
import time
import urllib.parse

HOST, PORT = "127.0.0.1", 9090
LOG = "/home/hatch/.kodi/temp/kodi.log"


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
    ok = True
    for line in open("/tmp/identity_kodi_test.txt"):
        name, url, expected = line.strip().split("|")
        with open(LOG, "rb") as f:
            f.seek(0, 2)
            marker = f.tell()
        play = ("plugin://plugin.video.kayifamily/?action=play&"
                + urllib.parse.urlencode({"url": url, "title": name}))
        rpc("Player.Open", {"item": {"file": play}}, 1)
        # wait up to 90s for active playback
        playing = False
        for _ in range(18):
            time.sleep(5)
            try:
                players = rpc("Player.GetActivePlayers", rid=2) or []
                props = rpc("Player.GetProperties",
                            {"playerid": 1,
                             "properties": ["time", "speed"]}, 3)
                t = props["time"]
                if (players and props["speed"] == 1
                        and (t["minutes"] * 60 + t["seconds"]) > 0):
                    playing = True
                    break
            except Exception:
                pass
        with open(LOG, "rb") as f:
            f.seek(marker)
            new_logs = f.read().decode("utf-8", "replace")
        m = re.search(
            r"Player host: ok\.ru \(embed https://ok\.ru/videoembed/(\d+)\)",
            new_logs)
        picked = m.group(1) if m else None
        ident_ok = playing and picked == expected
        print(("PASS " if ident_ok else "FAIL ") + name +
              " | picked=%s expected=%s playing=%s" % (picked, expected, playing))
        ok &= ident_ok
        try:
            rpc("Player.Stop", {"playerid": 1}, 4)
        except Exception:
            pass
        time.sleep(3)
    print("OVERALL:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
