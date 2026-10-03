# KayiFamily TV v0.1.0 — Release Notes

## STATUS

Proof-of-concept release candidate.

## TESTED

- Resolver: PASS
- Linux Kodi 20.5: PASS
- 5+ minute playback: PASS
- Pause/resume: PASS
- Seek: PASS
- Reopen: PASS
- Kodi restart + fresh resolution: PASS
- pytest: 8/8 PASS
- kodi-addon-checker: PASS (0 problems, 1 accepted PoC warning)

## NOT YET TESTED

- Chromecast with Google TV

## CURRENT CONTENT

- Mehmed Fetihler Sultani Episode 85 only

## KNOWN LIMITATIONS

- Full catalog not implemented yet
- OkRu currently used as working source
- VidMoly source currently broken upstream
- English subtitles are burned into the current test video
- Playback startup can take approximately 10–20 seconds
- Signed media URLs are temporary and re-resolved on every playback

Do not expect full catalog support in this release.
