"""Small logging helper that routes through Kodi's log when available.

Falls back to plain stderr/stdout so the resolver can also be unit-tested
outside of Kodi (e.g. `python3 -m resources.lib.resolver <episode_url>`).
"""

try:
    import xbmc

    def log(message, level=None):
        level = level if level is not None else xbmc.LOGINFO
        xbmc.log("[KayiFamily TV] %s" % message, level)

    def debug(message):
        try:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            enabled = addon.getSettingBool("debug")
        except Exception:
            enabled = True
        if enabled:
            xbmc.log("[KayiFamily TV][DEBUG] %s" % message, xbmc.LOGDEBUG)

except ImportError:  # running outside Kodi (tests / CLI)
    import sys

    def log(message, level=None):
        print("[KayiFamily TV] %s" % message, file=sys.stderr)

    def debug(message):
        print("[KayiFamily TV][DEBUG] %s" % message, file=sys.stderr)
