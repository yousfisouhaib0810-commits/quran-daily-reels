# Timing data

This directory is optional. If a timing file exists for the same EveryAyah
reciter ID and ayah, the generator uses it first. Otherwise it automatically
aligns the cached EveryAyah MP3 and produces a result without human review.

Supported JSON shapes include quran-align-style entries:

```json
[
  {
    "surah": 1,
    "ayah": 1,
    "segments": [[0, 1, 120, 630], [1, 2, 650, 1570]]
  }
]
```

Times are milliseconds relative to the individual ayah file. The audio
provider and reciter ID must match the MP3 used by the project.
