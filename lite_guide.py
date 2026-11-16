"""Make a small JSON guide for the Samsung TV app from guide.xml.gz.

Only channels in the playlist, only the next ~30 hours, so the TV can load it
quickly. Format: {"generated": epoch, "ch": {tvg_id: [[start, stop, title, desc], ...]}}
with start/stop in epoch seconds.
"""
import gzip
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

PLAYLIST = "https://seanjudelyons.github.io/tv/tv.m3u"
BEFORE, AFTER = 3 * 3600, 30 * 3600


def ts(s):
    return int(datetime.strptime(s.strip(), "%Y%m%d%H%M%S %z").timestamp())


def main(guide_path, out_path):
    req = urllib.request.Request(PLAYLIST, headers={"User-Agent": "tv-guide-lite/1.0"})
    m3u = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    wanted = set(re.findall(r'tvg-id="([^"]+)"', m3u))
    now = int(time.time())
    out = {}
    with gzip.open(guide_path) as f:
        for _, el in ET.iterparse(f):
            if el.tag != "programme":
                continue
            cid = el.get("channel")
            if cid in wanted:
                try:
                    a, b = ts(el.get("start")), ts(el.get("stop"))
                except Exception:
                    a = b = 0
                if b > now - BEFORE and a < now + AFTER:
                    title = (el.findtext("title") or "").strip()
                    sub = (el.findtext("sub-title") or "").strip()
                    desc = (el.findtext("desc") or "").strip()
                    if sub and sub != title:
                        desc = f"{sub}. {desc}" if desc else sub
                    out.setdefault(cid, []).append([a, b, title, desc[:220]])
            el.clear()
    for v in out.values():
        v.sort()
    with open(out_path, "w") as f:
        json.dump({"generated": now, "ch": out}, f, separators=(",", ":"), ensure_ascii=False)
    print(f"lite guide: {len(out)}/{len(wanted)} channels, {sum(map(len, out.values()))} programmes")
    if len(wanted) < 50 or len(out) < 50:
        sys.exit(f"lite guide looks broken: playlist ids {len(wanted)}, channels with programmes {len(out)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
