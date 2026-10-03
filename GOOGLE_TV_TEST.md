# KayiFamily TV — Google TV Test Guide

Release candidate: `plugin.video.kayifamily-0.1.0.zip` (Episode 85 proof of concept)

## What this tests

The exact proven chain, on your Chromecast with Google TV:

KayiFamily Episode 85 → OkRu source → fresh signed HLS → Kodi playback

## Install (beginner path)

Assumes Kodi is already installed on the Chromecast.

**A. Allow the add-on install (one time):**

1. Open **Kodi**
2. Go to **Settings** (gear icon) → **System** → **Add-ons**
3. Turn ON **Unknown sources** (confirm the warning)

**B. Get the ZIP onto the Chromecast (pick one):**

- *Option 1 — Downloader app:* open Downloader, enter the download link
  for `plugin.video.kayifamily-0.1.0.zip`, download it.
- *Option 2 — USB/network:* copy the ZIP to a USB stick or a network
  share the Chromecast can browse.

**C. Install in Kodi:**

1. In Kodi: **Add-ons** → **Install from zip file**
2. Select `plugin.video.kayifamily-0.1.0.zip` and install
3. Wait for the "Add-on installed" notification

**D. Play:**

1. **Add-ons** → **Video add-ons** → **KayiFamily TV**
2. **Test Series** → **Episode 85 (Test)** → **Play**

## Test checklist

INSTALL:
[ ] ZIP installs without errors
[ ] "KayiFamily TV" appears under Video add-ons (with icon)

NAVIGATION:
[ ] Remote navigates the menus
[ ] Episode entry opens

PLAYBACK:
[ ] Video starts (may take 10–20 seconds to resolve + buffer)
[ ] Stream plays (adaptive up to 1080p)
[ ] Audio works
[ ] English subtitles visible (burned into the video)
[ ] Pause works
[ ] Resume works
[ ] Seek forward/back works
[ ] Stop works

RELIABILITY:
[ ] Reopen the episode — plays again
[ ] Exit Kodi completely, reopen Kodi — episode plays again
      (proves the stream URL is re-resolved fresh each time)

NETWORK:
[ ] Works without VPN
[ ] No login requested at any point

## If something fails

- Note exactly which checklist step failed and what Kodi showed
  (any error popup text).
- In Kodi: **Settings → System → Logging → Enable debug logging**,
  reproduce, then share `kodi.log` — it contains `[KayiFamily TV]` lines
  showing the resolver chain (no passwords or tokens are logged).

## Known limitations (release candidate)

- Exactly one episode (Mehmed Fetihler Sultani, Episode 85). No catalog,
  search, or other series yet — those come after this test passes.
- The `moLy`/VidMoly source is broken upstream; the add-on uses the
  working `OkRu` source automatically.
- Temporary artwork (icon/fanart) — final branding comes later.
- First playback can take 10–20 seconds (live stream resolution + HLS startup).
