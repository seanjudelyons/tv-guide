"""Merge several free XMLTV guides into one guide.xml.gz, keeping only channels that are in the playlist.

TiviMate's free version accepts a single guide source, so this combines Australian free-to-air/FAST, Pluto TV,
Samsung TV Plus, Plex and epgshare01 (Australia/US/UK/Canada pay TV) guides into one file. Filtering to the
playlist's tvg-ids keeps the output small (the full sources are >100 MB uncompressed).

usage: merge_guide.py <out.xml.gz> [--fast] [<previous guide URL>]
--fast is the half-hourly refresh. About 40 Australian streaming channels (7plus: Judge Judy, NCIS, Bondi Rescue...)
only publish "now and the next two programmes", so a guide built every 6 hours shows nothing for them most of the
time. A fast run re-reads just the two Australian sources and takes every other channel from the guide published
by the last full run, so the big US/UK files are still downloaded only every 6 hours.

Old guide ids. A screen can hold an older copy of the playlist than the one on GitHub (TiviMate keeps the copy it
last downloaded; a playlist on a USB stick never changes). When a channel's tvg-id is changed in the playlist, such
a screen still asks for the old id. So the builder remembers every id each stream address has had (ids.json, next
to the guide) and publishes the channel's guide under the old ids as well. See known_ids().
"""
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.error
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
# Old guide ids (see the top of this file): the list committed with the code, and the one published by the last run.
IDS_SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_ids.json")
IDS_PUBLISHED = "https://raw.githubusercontent.com/seanjudelyons/tv-guide/guide/ids.json"


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


def playlist():
    """-> (every tvg-id in the playlist, {stream address: its tvg-id})"""
    req = urllib.request.Request(f"{PLAYLIST}?t={int(time.time())}", headers={"User-Agent": "tv-guide-merge/1.1"})
    m3u = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    pairs = re.findall(r'#EXTINF[^\n]*tvg-id="([^"]+)"[^\n]*\n(?:#[^\n]*\n)*(\S+)', m3u)
    return set(re.findall(r'tvg-id="([^"]+)"', m3u)), {url: cid for cid, url in pairs}


def known_ids(by_url):
    """{stream address: [every tvg-id it has had]}: the committed starting list (taken from the playlist's git
    history on 17 Nov 2026), plus what the last run published, plus the playlist as it is now. A missing ids.json
    is fine (first run); any other failure to read it stops the run, because publishing without it would forget
    the ids learned since the starting list."""
    known = {}
    with open(IDS_SEED, encoding="utf-8") as f:
        sources = [json.load(f)]
    for attempt in range(3):
        try:
            sources.append(json.loads(fetch(f"{IDS_PUBLISHED}?t={int(time.time())}")))
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
            err = e
        except Exception as e:
            err = e
        if attempt == 2:
            sys.exit(f"cannot read {IDS_PUBLISHED}: {err}")
        time.sleep(5)
    sources.append({url: [cid] for url, cid in by_url.items()})
    for src in sources:
        for url, ids in src.items():
            have = known.setdefault(url, [])
            have.extend(i for i in ids if i not in have)
    return known


def main(out_path, fast=False, base=PUBLISHED):
    wanted, by_url = playlist()
    known = known_ids(by_url)
    # An old id whose stream is still in the playlist is a copy of that channel's guide (made after the merge).
    # An old id whose stream has gone is kept like any other channel, in case a source still lists it.
    alias = {old: by_url[url] for url, ids in known.items() if url in by_url
             for old in ids if old != by_url[url] and old not in wanted}
    current, wanted = wanted, wanted | ({i for ids in known.values() for i in ids} - set(alias))
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
    olds = {}
    for old, new in alias.items():
        olds.setdefault(new, []).append(old)
    for el in list(channels.values()) + programmes[:]:
        key = "id" if el.tag == "channel" else "channel"
        for old in olds.get(el.get(key), ()):
            twin = ET.Element(el.tag, dict(el.attrib, **{key: old}))  # its own attributes, the same children
            twin.text, twin.tail = el.text, el.tail
            twin.extend(el)
            if el.tag == "channel":
                channels[old] = twin
            else:
                programmes.append(twin)
    tv = ET.Element("tv", {"generator-info-name": "tv-guide-merge"})
    tv.extend(channels.values())
    tv.extend(programmes)
    with gzip.open(out_path, "wb", compresslevel=9) as f:
        ET.ElementTree(tv).write(f, encoding="utf-8", xml_declaration=True)
    kept = sorted(c for c, u in owner.items() if u == base)
    if kept and not fast:
        print(f"kept from the last published guide (no fresh data): {len(kept)} channels: {', '.join(kept[:60])}")
    with open(os.path.join(os.path.dirname(os.path.abspath(out_path)), "ids.json"), "w", encoding="utf-8") as f:
        json.dump(known, f, separators=(",", ":"), sort_keys=True)
    served = sum(1 for new in alias.values() if new in owner) + len((wanted - current) & set(owner))
    print(f"guide: {len(current & set(owner))}/{len(current)} playlist channels have programmes ({len(channels)} defined), {len(programmes)} programmes")
    print(f"old ids: {served} of {len(alias) + len(wanted - current)} also have a guide ({len(alias)} are copies of the channel's current id)")
    # Fail loudly (so GitHub emails/opens an issue) rather than publish a broken guide
    # (a fast run without the published guide would be missing most channels, so that is a failure too)
    if len(programmes) < 10000 or len(failed) > len(sources) // 2 or (fast and base in failed):
        sys.exit(f"guide looks broken: {len(programmes)} programmes, failed sources: {failed}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--fast"]
    main(args[0] if args else "guide.xml.gz", "--fast" in sys.argv, args[1] if len(args) > 1 else PUBLISHED)
