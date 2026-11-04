# Metadata and size comparison

Regenerated existing 30-file corpus. Expected durations derive from generator inputs; raw AVC is excluded from the duration score. Requested-tag score is out of 90, including containers that did not retain the requested tags. Agreement is not correctness.

| Metric | libav | MediaInfo |
|---|---:|---:|
| Extracted files / 30 | 30 | 30 |
| Correct codecs / 30 | 30 | 30 |
| Correct rounded durations / 29 | 28 | 29 |
| Requested tags recovered / 90 | 64 | 73 |
| Stripped helper bytes | 1,851,752 | 7,059,760 |
| gzip -9 bytes | 850,159 | 2,858,446 |

## Differences

| File | Field | libav | MediaInfo |
|---|---|---|---|
| 05-xvid-mp3.avi | album | '' | 'Spike Album' |
| 06-mpeg4-mp3.avi | album | '' | 'Spike Album' |
| 11-wmv2-wmav2.wmv | bitrate_kbps | 437 | 439 |
| 12-theora-vorbis.ogv | artist | '' | 'Spike Artist' |
| 12-theora-vorbis.ogv | album | '' | 'Spike Album' |
| 12-theora-vorbis.ogv | title | '' | 'Spike Title' |
| 13-h264-aac.flv | bitrate_kbps | 805 | 804 |
| 16-mjpeg-pcm.avi | album | '' | 'Spike Album' |
| 17-h263-aac.3gp | artist | '' | 'Spike Artist' |
| 17-h263-aac.3gp | album | '' | 'Spike Album' |
| 17-h263-aac.3gp | title | '' | 'Spike Title' |
| 18-cbr-cover.mp3 | bitrate_kbps | 193 | 192 |
| 20-vbr-noxing.mp3 | length_seconds | 60 | 62 |
| 20-vbr-noxing.mp3 | bitrate_kbps | 37 | 36 |
