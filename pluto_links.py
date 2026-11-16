"""Resolve the playlist's Pluto TV redirect links (jmp2.uk/plu-<id>.m3u8) to Pluto's real stream address.

The Samsung TV app can't follow those redirects itself (no CORS on the redirect), so this publishes
pluto.json: {"generated": epoch, "urls": {channel_id: stream_url}}. Pluto's session tokens last ~24h
and this runs every 6h, so the links stay fresh.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PLAYLIST = "https://seanjudelyons.github.io/tv/tv.m3u"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(NoRedirect)


def resolve(cid):
    req = urllib.request.Request(f"https://jmp2.uk/plu-{cid}.m3u8", headers={"User-Agent": "Mozilla/5.0"})
    try:
        opener.open(req, timeout=30)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return cid, e.headers.get("Location")
    except Exception as e:
        print(f"skip {cid}: {e}", file=sys.stderr)
    return cid, None


def main(out_path):
    req = urllib.request.Request(f"{PLAYLIST}?t={int(time.time())}", headers={"User-Agent": "tv-pluto-links/1.0"})
    m3u = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    ids = sorted(set(re.findall(r"jmp2\.uk/plu-([0-9a-f]{24})", m3u)))
    with ThreadPoolExecutor(8) as ex:
        urls = {cid: url for cid, url in ex.map(resolve, ids) if url}
    with open(out_path, "w") as f:
        json.dump({"generated": int(time.time()), "urls": urls}, f, separators=(",", ":"))
    print(f"pluto links: {len(urls)}/{len(ids)} resolved")
    if ids and len(urls) < len(ids) // 2:
        sys.exit(f"pluto links look broken: only {len(urls)}/{len(ids)} resolved")


if __name__ == "__main__":
    main(sys.argv[1])
