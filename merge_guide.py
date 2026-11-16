"""Merge several free XMLTV guides into one guide.xml.gz, keeping only channels that are in the playlist.

TiviMate's free version accepts a single guide source, so this combines Australian free-to-air/FAST, Pluto TV,
Samsung TV Plus, Plex and epgshare01 (US/UK/Canada cable) guides into one file. Filtering to the playlist's
tvg-ids keeps the output small (the full sources are >100 MB uncompressed).
"""
import gzip
import io
import re
import sys
import time
import urllib.request
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
    "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
    "https://i.mjh.nz/SamsungTVPlus/gb.xml.gz",
    "https://i.mjh.nz/SamsungTVPlus/in.xml.gz",
    "https://i.mjh.nz/Plex/au.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz",
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tv-guide-merge/1.1"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def playlist_ids():
    req = urllib.request.Request(f"{PLAYLIST}?t={int(time.time())}", headers={"User-Agent": "tv-guide-merge/1.1"})
    m3u = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    return set(re.findall(r'tvg-id="([^"]+)"', m3u))


def main(out_path):
    wanted = playlist_ids()
    channels, programmes, owner, failed = {}, [], {}, []  # owner: channel id -> source supplying its programmes
    for url in SOURCES:
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
                if cid in wanted and owner.setdefault(cid, url) == url:
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
    print(f"guide: {len(owner)}/{len(wanted)} playlist channels have programmes ({len(channels)} defined), {len(programmes)} programmes")
    # Fail loudly (so GitHub emails/opens an issue) rather than publish a broken guide
    if len(programmes) < 10000 or len(failed) > len(SOURCES) // 2:
        sys.exit(f"guide looks broken: {len(programmes)} programmes, {len(failed)} sources failed")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "guide.xml.gz")
