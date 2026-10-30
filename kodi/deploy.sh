#!/bin/sh
# Deploy the Kodi-side config files in this directory to the LibreELEC box.
#
#   ./kodi/deploy.sh [host]        # host defaults to 192.168.1.181
#
# Files deployed:
#   advancedsettings.xml -> /storage/.kodi/userdata/advancedsettings.xml   (read only at Kodi start)
#   keymaps/livetv.xml   -> /storage/.kodi/userdata/keymaps/livetv.xml
#
# Everything else about the client (display mode, refresh switching, PVR settings, addon
# settings) is applied through JSON-RPC / addon settings and documented in ../docs/reference.md.
set -eu

HOST="${1:-192.168.1.181}"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
USERDIR=/storage/.kodi/userdata

echo "==> deploying to root@$HOST"

ssh "root@$HOST" "mkdir -p $USERDIR/keymaps"

scp "$HERE/advancedsettings.xml" "root@$HOST:$USERDIR/advancedsettings.xml"
scp "$HERE/keymaps/livetv.xml"   "root@$HOST:$USERDIR/keymaps/livetv.xml"

# advancedsettings.xml is only parsed at startup, so restart Kodi to apply it.
ssh "root@$HOST" 'systemctl restart kodi'

echo "==> deployed. verify with:"
echo "    ssh root@$HOST 'grep \"Loaded settings file\" /storage/.kodi/temp/kodi.log'"
echo "    ssh root@$HOST 'grep -oE \"GUI format [0-9x]+, Display [0-9x]+ @ [0-9.]+ Hz\" /storage/.kodi/temp/kodi.log | tail -1'"
echo "    ssh root@$HOST 'dmesg | grep -ci segfault'   # must not increase"
