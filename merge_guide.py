"""Merge several free XMLTV guides (from i.mjh.nz) into one guide.xml.gz.

TiviMate's free version accepts a single guide source, so this combines the
Australian free-to-air, Pluto TV, Samsung TV Plus and Plex guides into one file.
"""
import gzip
import sys
import urllib.request
import xml.etree.ElementTree as ET

SOURCES = [
    "https://i.mjh.nz/au/Sydney/epg.xml.gz",
    "https://i.mjh.nz/PlutoTV/us.xml.gz",
    "https://i.mjh.nz/PlutoTV/ca.xml.gz",
    "https://i.mjh.nz/PlutoTV/gb.xml.gz",
    "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
    "https://i.mjh.nz/SamsungTVPlus/gb.xml.gz",
    "https://i.mjh.nz/SamsungTVPlus/in.xml.gz",
    "https://i.mjh.nz/Plex/au.xml.gz",
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tv-guide-merge/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def main(out_path):
    channels, programmes = {}, []
    owner = {}  # channel id -> source that supplied it, so overlapping regions don't duplicate
    for url in SOURCES:
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:  # one broken source shouldn't break the whole guide
            print(f"skip {url}: {e}", file=sys.stderr)
            continue
        for ch in root.findall("channel"):
            cid = ch.get("id")
            if cid not in channels:
                channels[cid] = ch
                owner[cid] = url
        for p in root.findall("programme"):
            if owner.get(p.get("channel")) == url:
                programmes.append(p)
        print(f"{url}: total {len(channels)} channels, {len(programmes)} programmes")
    tv = ET.Element("tv", {"generator-info-name": "tv-guide-merge"})
    tv.extend(channels.values())
    tv.extend(programmes)
    with gzip.open(out_path, "wb", compresslevel=9) as f:
        ET.ElementTree(tv).write(f, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "guide.xml.gz")
