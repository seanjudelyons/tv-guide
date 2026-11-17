# tv-guide

GitHub Action (every 30 minutes; a full rebuild every 6 hours, quick refreshes in between) that publishes to the
`guide` branch:

| File | Made by | Used by |
|---|---|---|
| `guide.xml.gz` | `merge_guide.py` — merges free guides: i.mjh.nz (AU Sydney, Pluto US/CA/GB/SE, Samsung TV Plus US/GB/IN, Plex AU/US) and epgshare01 (AU, US, UK, CA) | TiviMate / Kodi (single EPG source) |
| `guide.json` | `lite_guide.py` — next ~30 h for channels in the playlist only | Samsung TV app |
| `pluto.json` | `pluto_links.py` — resolves the playlist's jmp2.uk Pluto redirects (tokens last ~24 h) | Samsung TV app |

**Quick refresh.** About 40 Australian streaming channels only publish "now and the next two programmes", so
`merge_guide.py --fast` re-reads just the two Australian sources every 30 minutes and takes everything else from
the guide published last time. **Safety net.** Every run reads the last published guide as its final source, so a
channel whose provider drops out upstream keeps its known programmes instead of going blank.

Each script fails the run if its output looks broken. On failure the workflow opens a `tv-alert` issue that
@mentions the owner (email); the next successful run closes it. Test with
`gh workflow run guide.yml -f simulate_failure=true`.
