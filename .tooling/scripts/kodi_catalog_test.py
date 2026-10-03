#!/usr/bin/env python3
"""Test the v0.2.0 catalog navigation on headless Kodi via JSON-RPC.

Exercises: root menu, shows, seasons, episodes, latest, documentaries.
Playback is tested separately per episode.
"""

import json
import socket
import sys
import urllib.parse

HOST, PORT = "127.0.0.1", 9090
BASE = "plugin://plugin.video.kayifamily/"


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
    # unreachable


def ls(action_url):
    res = rpc("Files.GetDirectory",
              {"directory": action_url,
               "properties": ["title", "art"]}, 7)
    return res.get("files") or []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))
    return cond


def main():
    ok = True
    rpc("Addons.SetAddonEnabled",
        {"addonid": "plugin.video.kayifamily", "enabled": True}, 1)

    root = ls(BASE)
    labels = [f.get("label") for f in root]
    ok &= check("root menu (4 items)", len(root) == 4, labels)

    shows = ls(BASE + "?action=shows")
    ok &= check("shows list", len(shows) == 3, "%d shows" % len(shows))
    art = (shows[0].get("art") or {}) if shows else {}
    ok &= check("show artwork present", bool(art.get("poster")), list(art.keys()))

    seasons = ls(BASE + "?action=show&" + urllib.parse.urlencode({"show_id": "mehmed-fetihler-sultani"}))
    ok &= check("mehmed seasons", len(seasons) == 4, "%d seasons" % len(seasons))

    eps = ls(BASE + "?action=season&" + urllib.parse.urlencode(
        {"show_id": "payitaht-abdulhamid", "season": "5"}))
    ok &= check("payitaht S5 episodes", len(eps) > 20, "%d episodes" % len(eps))
    ep_art = (eps[0].get("art") or {}) if eps else {}
    ok &= check("episode artwork present", bool(ep_art.get("thumb")), list(ep_art.keys()))

    latest = ls(BASE + "?action=latest")
    ok &= check("latest episodes", len(latest) == 30, "%d items" % len(latest))

    docs = ls(BASE + "?action=docs")
    ok &= check("documentaries (empty, site API)", len(docs) == 0, "%d items" % len(docs))

    meh = ls(BASE + "?action=season&" + urllib.parse.urlencode(
        {"show_id": "mehmed-fetihler-sultani", "season": "4"}))
    meh_labels = [f.get("label") for f in meh]
    ok &= check("mehmed S4 has Episode 85", any("85" in (l or "") for l in meh_labels),
                meh_labels)

    print("OVERALL:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
