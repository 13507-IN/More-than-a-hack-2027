# Match data

The licensed match bundle is **not** in this repository. Unpack it here:

```
data/
  tactical/
    BAR-ATH_tactical.mp4
    BAR-ATH_tactical_atd.xml
    BAR-ATH_tactical_atd.txt
    BAR-ATH_tactical_homography.csv
    BAR-ATH_tactical_smart_tagging.xml
  broadcast/
    BAR-ATH_broadcast.mp4
    BAR-ATH_broadcast_atd.xml
    BAR-ATH_broadcast_atd.txt
    BAR-ATH_broadcast_homography.csv
```

Or put it anywhere and set `MTAH_DATA_DIR`:

```powershell
$env:MTAH_DATA_DIR = "D:\mtah2027"
```

The evaluation scorer needs no data. The submission pipeline does:

```powershell
.\.venv\Scripts\python.exe -m solution.pipeline
```

Everything under `data/` except this file is gitignored. Do not commit or
redistribute the match assets; they are covered by the terms you accepted at
enrolment.
