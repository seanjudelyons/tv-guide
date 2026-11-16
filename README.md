# tv-guide

GitHub Action (every 6 hours) that publishes to the `guide` branch:

| File | Made by | Used by |
|---|---|---|
| `guide.xml.gz` | `merge_guide.py` — merges free i.mjh.nz guides (AU Sydney, Pluto US/CA/GB, Samsung TV Plus US/GB/IN, Plex AU) | TiviMate / Kodi (single EPG source) |
| `guide.json` | `lite_guide.py` — next ~30 h for channels in the playlist only | Samsung TV app |
| `pluto.json` | `pluto_links.py` — resolves the playlist's jmp2.uk Pluto redirects (tokens last ~24 h) | Samsung TV app |

Each script fails the run if its output looks broken. On failure the workflow opens a `tv-alert` issue that
@mentions the owner (email); the next successful run closes it. Test with
`gh workflow run guide.yml -f simulate_failure=true`.
