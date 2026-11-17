"""Merge several free XMLTV guides into one guide.xml.gz, keeping only channels that are in the playlist.

TiviMate's free version accepts a single guide source, so this combines Australian free-to-air/FAST, Pluto TV,
Samsung TV Plus, Plex and epgshare01 (Australia/US/UK/Canada pay TV) guides into one file. Filtering to the
playlist's tvg-ids keeps the output small (the full sources are >100 MB uncompressed).

usage: merge_guide.py <out.xml.gz> [--fast] [<previous guide URL>]
--fast is the half-hourly refresh. About 40 Australian streaming channels (7plus: Judge Judy, NCIS, Bondi Rescue...)
only publish "now and the next two programmes", so a guide built every 6 hours shows nothing for them most of the
time. A fast run re-reads just the two Australian sources and takes every other channel from the guide published
by the last full run, so the big US/UK files are still downloaded only every 6 hours.
"""
import gzip
import io
import re
import sys
import time
import urllib.request
from datetime import datetime
import xml.etree.ElementTree as ET

PLAYLIST = "https://seanjudelyons.github.io/tv/tv.m3u"

# Order matters: for each channel, programmes come from the first source that has any for it
# (so overlapping regions don't duplicate, and a source listing a channel with no programmes doesn't block others).
SOURCES = [
    "https://i.mjh.nz/au/Sydney/epg.xml.gz",
    "https://i.mjh.nz/au/all/epg.xml.gz",
    "https://i.mjh.nz/PlutoTV/us.xml.gz",
    "https://i.mjh.nz/PlutoTV/ca.xml.gz",
    "https://i.mjh.nz/PlutoTV/gb.xml.gz",
    "https://i.mjh.nz/PlutoTV/se.xml.gz",   # NonStop Kung Fu is a Swedish Pluto channel
    "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
    "https://i.mjh.nz/SamsungTVPlus/gb.xml.gz",
    "https://i.mjh.nz/SamsungTVPlus/in.xml.gz",
    "https://i.mjh.nz/Plex/au.xml.gz",
    "https://i.mjh.nz/Plex/us.xml.gz",      # 24 Hour Free Movies, Camp Spoopy
    "https://epgshare01.online/epgshare01/epg_ripper_AU1.xml.gz",   # BBC News, Bloomberg, France 24, CNA, Sky Racing...
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz",
]


FAST_SOURCES = SOURCES[:2]  # the Australian ones; see --fast above
# The guide this workflow published last time. Always read last, as a safety net: i.mjh.nz sometimes drops a whole
# provider for a few hours (17 Nov 2026: all 46 10 play channels had no programmes), and without this every such
# gap would blank those channels until the provider came back. Programmes that ended over 6 hours ago are dropped.
PUBLISHED = "https://raw.githubusercontent.com/seanjudelyons/tv-guide/guide/guide.xml.gz"
KEEP_ENDED = 6 * 3600


def ended_at(el):
    try:
        return datetime.strptime(el.get("stop").strip(), "%Y%m%d%H%M%S %z").timestamp()
    except Exception:
        return float("inf")  # unreadable time: keep the programme


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tv-guide-merge/1.1"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def playlist_ids():
    req = urllib.request.Request(f"{PLAYLIST}?t={int(time.time())}", headers={"User-Agent": "tv-guide-merge/1.1"})
    m3u = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    return set(re.findall(r'tvg-id="([^"]+)"', m3u))


def main(out_path, fast=False, base=PUBLISHED):
    wanted = playlist_ids()
    channels, programmes, owner, failed = {}, [], {}, []  # owner: channel id -> source supplying its programmes
    sources = (FAST_SOURCES if fast else SOURCES) + [base]
    cutoff = time.time() - KEEP_ENDED
    for url in sources:
        try:
            data = fetch(url)
        except Exception as e:  # one broken source shouldn't break the whole guide
            print(f"skip {url}: {e}", file=sys.stderr)
            failed.append(url)
            continue
        added = 0
        for _, el in ET.iterparse(io.BytesIO(data)):
            if el.tag == "channel":
                cid = el.get("id")
                if cid in wanted and cid not in channels:
                    channels[cid] = el
                    added += 1
                    continue  # keep element (don't clear)
            elif el.tag == "programme":
                cid = el.get("channel")
                if cid in wanted and (url != base or ended_at(el) > cutoff) and owner.setdefault(cid, url) == url:
                    programmes.append(el)
                    continue
            else:
                continue
            el.clear()
        del data
        print(f"{url}: +{added} channels, totals {len(channels)} channels / {len(programmes)} programmes")
    tv = ET.Element("tv", {"generator-info-name": "tv-guide-merge"})
    tv.extend(channels.values())
    tv.extend(programmes)
    with gzip.open(out_path, "wb", compresslevel=9) as f:
        ET.ElementTree(tv).write(f, encoding="utf-8", xml_declaration=True)
    kept = sorted(c for c, u in owner.items() if u == base)
    if kept and not fast:
        print(f"kept from the last published guide (no fresh data): {len(kept)} channels: {', '.join(kept[:60])}")
    print(f"guide: {len(owner)}/{len(wanted)} playlist channels have programmes ({len(channels)} defined), {len(programmes)} programmes")
    # Fail loudly (so GitHub emails/opens an issue) rather than publish a broken guide
    # (a fast run without the published guide would be missing most channels, so that is a failure too)
    if len(programmes) < 10000 or len(failed) > len(sources) // 2 or (fast and base in failed):
        sys.exit(f"guide looks broken: {len(programmes)} programmes, failed sources: {failed}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--fast"]
    main(args[0] if args else "guide.xml.gz", "--fast" in sys.argv, args[1] if len(args) > 1 else PUBLISHED)
