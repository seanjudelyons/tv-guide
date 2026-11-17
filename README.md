# tv-guide

GitHub Action (every 30 minutes; a full rebuild every 6 hours, quick refreshes in between) that publishes to the
`guide` branch:

| File | Made by | Used by |
|---|---|---|
| `guide.xml.gz` | `merge_guide.py` — merges free guides: i.mjh.nz (AU Sydney, Pluto US/CA/GB/SE, Samsung TV Plus US/GB/IN, Plex AU/US) and epgshare01 (AU, US, UK, CA) | TiviMate / Kodi (single EPG source) |
| `guide.json` | `lite_guide.py` — next ~30 h for channels in the playlist only | Samsung TV app |
| `pluto.json` | `pluto_links.py` — resolves the playlist's jmp2.uk Pluto redirects (tokens last ~24 h) | Samsung TV app |
| `ids.json` | `merge_guide.py` — every guide id each stream address has had | the next run of `merge_guide.py` |

**Quick refresh.** About 40 Australian streaming channels only publish "now and the next two programmes", so
`merge_guide.py --fast` re-reads just the two Australian sources every 30 minutes and takes everything else from
the guide published last time. **Safety net.** Every run reads the last published guide as its final source, so a
channel whose provider drops out upstream keeps its known programmes instead of going blank.

**Old guide ids.** A screen can hold an older copy of the playlist than the one on GitHub (TiviMate keeps the copy
it last downloaded). When a channel's `tvg-id` changes in the playlist, that screen still asks for the old id, so
`guide.xml.gz` carries the channel's guide under its old ids too. The builder learns old ids by itself: each run
adds the playlist's current ids to `ids.json`. `known_ids.json` is the starting list (from the playlist's git
history up to 17 Nov 2026) and the fallback if the `guide` branch is ever recreated.

Each script fails the run if its output looks broken. On failure the workflow opens a `tv-alert` issue that
@mentions the owner (email); the next successful run closes it. Test with
`gh workflow run guide.yml -f simulate_failure=true`.
