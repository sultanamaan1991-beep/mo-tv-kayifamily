#!/usr/bin/env python3
"""Build docs/catalog.json for the KayiFamily TV Kodi add-on.

Reads ONLY public WordPress REST API metadata from kayifamilytv.com:
show/season categories, episode posts (title, link, date, featured image).
No video streams, no signed URLs, no authentication -- playback URLs are
never stored; Kodi resolves them fresh via resolver.py at Play time.

Usage:
    python3 tools/build_catalog.py [--out docs/catalog.json]

Exit status / stdout:
    prints CHANGED or UNCHANGED (used by the update-catalog workflow).
"""

import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://kayifamilytv.com/wp-json/wp/v2"
SHOWS_PARENT = 7          # HISTORICAL TV SHOWS (English)
DOCS_CATEGORY = 54        # Documentaries
OUT = "docs/catalog.json"

# Category slugs containing any of these are non-English duplicates.
EXCLUDE_HINTS = ("espanol", "español", "portugues", "português")

EPISODE_RE = re.compile(r"-episode-(\d+)", re.IGNORECASE)
SEASON_RE = re.compile(r"season\s*(\d+)", re.IGNORECASE)
SKIP_TITLE_RE = re.compile(r"trailer|promo|teaser|\bost\b|news|recap", re.IGNORECASE)

UA = {"User-Agent": "KayiFamilyTV-catalog-builder/1.0 (+kodi addon)"}


def api_get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp), resp.headers


def api_get_all(path, params=None):
    """GET with WP pagination (X-WP-TotalPages)."""
    params = dict(params or {})
    params.setdefault("per_page", 100)
    items, headers = api_get(path, params)
    total_pages = int(headers.get("X-WP-TotalPages", "1") or 1)
    for page in range(2, total_pages + 1):
        page_items, _ = api_get(path, dict(params, page=page))
        items.extend(page_items)
    return items


def clean_show_title(name):
    return " ".join(name.title().split())


def show_id_from_slug(slug):
    slug = slug.lower()
    for suffix in ("-english-subtitles", "-turkish-historical-tv-shows", "-english"):
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)]
    return slug.strip("-") or slug


def is_english_show(cat):
    slug = cat["slug"].lower()
    return not any(h in slug for h in EXCLUDE_HINTS)


def episode_number(post):
    m = EPISODE_RE.search(post.get("slug", ""))
    if m:
        return int(m.group(1))
    m = re.search(r"episode\s*(\d+)", post.get("title", {}).get("rendered", ""), re.I)
    return int(m.group(1)) if m else None


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_media(media_ids):
    """Batch-fetch media -> {id: {'thumb': ..., 'full': ...}}."""
    result = {}
    ids = sorted({i for i in media_ids if i})
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        items, _ = api_get(
            "/media",
            {"include": ",".join(map(str, chunk)), "per_page": 100,
             "_fields": "id,source_url,media_details"},
        )
        for m in items:
            sizes = (m.get("media_details") or {}).get("sizes") or {}
            thumb = (sizes.get("medium") or {}).get("source_url") or m.get("source_url")
            large = (sizes.get("large") or {}).get("source_url") or m.get("source_url")
            result[m["id"]] = {"thumb": thumb, "full": large}
    return result


def build():
    categories = api_get_all("/categories", {
        "_fields": "id,name,slug,parent,count,description"})
    by_id = {c["id"]: c for c in categories}

    shows = []
    all_media_ids = []
    season_posts = {}  # season_cat_id -> posts

    show_cats = [c for c in categories
                 if c["parent"] == SHOWS_PARENT and is_english_show(c)]
    show_cats.sort(key=lambda c: clean_show_title(c["name"]))

    for show in show_cats:
        seasons = [c for c in categories if c["parent"] == show["id"]]
        season_objs = []
        for season in seasons:
            m = SEASON_RE.search(season["name"] or "")
            if not m:
                continue
            posts = api_get_all("/posts", {
                "categories": season["id"],
                "_fields": "id,date,slug,link,title,featured_media",
            })
            season_posts[season["id"]] = posts
            all_media_ids.extend(p.get("featured_media") for p in posts)
            season_objs.append((int(m.group(1)), season, posts))
        if not season_objs:
            # No season sub-categories: episodes live directly in the show
            # category (e.g. Destan, Hayreddin). Treat as Season 1.
            posts = api_get_all("/posts", {
                "categories": show["id"],
                "_fields": "id,date,slug,link,title,featured_media",
            })
            all_media_ids.extend(p.get("featured_media") for p in posts)
            season_objs.append((1, show, posts))
        shows.append((show, sorted(season_objs)))

    # documentaries (flat)
    doc_posts = api_get_all("/posts", {
        "categories": DOCS_CATEGORY,
        "_fields": "id,date,slug,link,title,featured_media",
    })
    all_media_ids.extend(p.get("featured_media") for p in doc_posts)

    media = fetch_media(all_media_ids)

    def ep_obj(post):
        num = episode_number(post)
        fm = media.get(post.get("featured_media") or 0, {})
        return {
            "number": num,
            "title": strip_tags(post.get("title", {}).get("rendered")),
            "url": post.get("link"),
            "thumb": fm.get("thumb"),
            "published": (post.get("date") or "")[:10],
        }

    catalog_shows = []
    latest = []
    for show, season_objs in shows:
        sid = show_id_from_slug(show["slug"])
        stitle = clean_show_title(show["name"])
        seasons_out = []
        for season_no, season, posts in season_objs:
            eps = []
            for p in posts:
                if SKIP_TITLE_RE.search(strip_tags(p.get("title", {}).get("rendered"))):
                    continue
                e = ep_obj(p)
                if e["number"] is None or not e["url"]:
                    continue
                eps.append(e)
                full = dict(e)
                full.update({"show_id": sid, "show_title": stitle,
                             "season": season_no})
                latest.append(full)
            eps.sort(key=lambda e: e["number"])
            if eps:
                seasons_out.append({"number": season_no, "episodes": eps})
        seasons_out.sort(key=lambda s: s["number"])
        # show art: newest episode's thumbnail
        show_eps = [e for e in latest if e["show_id"] == sid and e["thumb"]]
        art = show_eps[-1]["thumb"] if show_eps else None
        if not seasons_out:
            continue  # e.g. movie-only categories: no episodes to list
        catalog_shows.append({
            "id": sid,
            "title": stitle,
            "description": strip_tags(show.get("description")),
            "poster": art,
            "fanart": art,
            "seasons": seasons_out,
        })

    latest.sort(key=lambda e: e["published"], reverse=True)
    latest = latest[:30]

    docs = []
    for p in doc_posts:
        e = ep_obj(p)
        if e["url"]:
            docs.append(e)

    catalog = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": API,
        "shows": catalog_shows,
        "documentaries": docs,
        "latest": latest,
    }
    return catalog


def main():
    out = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--out" else OUT
    catalog = build()
    new_body = {k: v for k, v in catalog.items() if k != "generated"}
    changed = True
    try:
        old = json.load(open(out))
        old_body = {k: v for k, v in old.items() if k != "generated"}
        changed = (
            hashlib.sha256(json.dumps(new_body, sort_keys=True).encode()).hexdigest()
            != hashlib.sha256(json.dumps(old_body, sort_keys=True).encode()).hexdigest()
        )
    except (FileNotFoundError, ValueError):
        pass
    if changed:
        with open(out, "w") as f:
            json.dump(catalog, f, indent=1, ensure_ascii=False)
            f.write("\n")
    n_shows = len(catalog["shows"])
    n_seasons = sum(len(s["seasons"]) for s in catalog["shows"])
    n_eps = sum(len(se["episodes"]) for s in catalog["shows"] for se in s["seasons"])
    print("shows=%d seasons=%d episodes=%d documentaries=%d latest=%d -> %s"
          % (n_shows, n_seasons, n_eps, len(catalog["documentaries"]),
             len(catalog["latest"]), "CHANGED" if changed else "UNCHANGED"))


if __name__ == "__main__":
    main()
