#!/usr/bin/env bash
# One-shot: write Jellyfin.Xtream.Library plugin config with STRONG8K credentials
# pulled from Dispatcharr's DB. Credentials are never printed.
set -euo pipefail

CREDS=$(docker exec -i dispatcharr python manage.py shell <<'EOF'
from apps.m3u.models import M3UAccount
a = M3UAccount.objects.get(pk=2)
base = a.server_url.split('get.php')[0].rstrip('/')
print(base)
print(a.username)
print(a.password)
EOF
)

# The manage.py shell prints banner lines on stdout; our three values are last.
BASE=$(echo "$CREDS" | grep -v '^$' | tail -n 3 | sed -n 1p)
USER=$(echo "$CREDS" | grep -v '^$' | tail -n 3 | sed -n 2p)
PASS=$(echo "$CREDS" | grep -v '^$' | tail -n 3 | sed -n 3p)
echo "$BASE" | grep -q '^http' || { echo 'FAILED: bad BaseUrl'; exit 1; }
if [ -z "$USER" ] || [ -z "$PASS" ]; then echo 'FAILED to get creds'; exit 1; fi

CFG=/home/hadev/Projects/Lab/iptv-stack/jellyfin/config/plugins/configurations/Jellyfin.Xtream.Library.xml

sudo -n tee "$CFG" > /dev/null <<XML
<?xml version="1.0" encoding="utf-8"?>
<PluginConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Providers />
  <SyncIntervalMinutes>60</SyncIntervalMinutes>
  <TriggerLibraryScan>true</TriggerLibraryScan>
  <!-- Manual, not Daily: the scheduled sync trips the provider's abuse block (403s our
       IPv4 and kills live TV). Run it via scripts/sync-vod.sh instead. -->
  <SyncScheduleType>Manual</SyncScheduleType>
  <SyncDailyHour>4</SyncDailyHour>
  <SyncDailyMinute>30</SyncDailyMinute>
  <EnableMetadataLookup>true</EnableMetadataLookup>
  <MetadataCacheAgeDays>30</MetadataCacheAgeDays>
  <MetadataParallelism>3</MetadataParallelism>
  <EnableLiveTv>false</EnableLiveTv>
  <EnableNativeTuner>false</EnableNativeTuner>
  <BaseUrl>$BASE</BaseUrl>
  <Username>$USER</Username>
  <Password>$PASS</Password>
  <UserAgent>Mozilla/5.0</UserAgent>
  <LibraryPath>/media/vod-strm</LibraryPath>
  <SyncMovies>true</SyncMovies>
  <SyncSeries>true</SyncSeries>
  <SelectedVodCategoryIds>
    <Int32>285</Int32>
    <Int32>163</Int32>
  </SelectedVodCategoryIds>
  <SelectedSeriesCategoryIds>
    <Int32>138</Int32>
  </SelectedSeriesCategoryIds>
  <SyncParallelism>10</SyncParallelism>
  <RequestDelayMs>50</RequestDelayMs>
  <MaxRetries>3</MaxRetries>
  <RetryDelayMs>1000</RetryDelayMs>
</PluginConfiguration>
XML

echo "written (cred lines present: $(sudo -n grep -cE 'Username|Password' "$CFG"))"
