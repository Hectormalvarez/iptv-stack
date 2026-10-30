#!/bin/sh
# Bring-up / diagnostics for HDMI-CEC on the LibreELEC Kodi box (Vizio TV).
#
# Run this ON THE BOX (ssh root@192.168.1.181), or from the workstation via:
#   scp scripts/cec-vizio-bringup.sh root@192.168.1.181:/storage/ && \
#   ssh root@192.168.1.181 'sh /storage/cec-vizio-bringup.sh'
#
# Default mode is READ-ONLY diagnostics (safe to run with no adapter attached).
#   sh cec-vizio-bringup.sh                 # diagnose only
#   sh cec-vizio-bringup.sh --apply-vizio   # set CEC device type to Playback (4)
#
# Why --apply-vizio exists: Vizio TVs ignore the CEC adapter when Kodi/libCEC
# registers as a *Recording* device (libCEC default). Several Vizio models
# (P55-F1, PX65, P-Series Quantum, E-series) need *Playback* instead, otherwise
# the TV lists Kodi as a CEC device but the remote does nothing. Kodi must be
# stopped while editing the settings file or the change is discarded on reboot.

set -u

PERIPH_DIR=/storage/.kodi/userdata/peripheral_data
BACKUP_DIR=/storage/backups/cec
MODE=diagnose
[ "${1:-}" = "--apply-vizio" ] && MODE=apply

say() { printf '%s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

say "=== HDMI-CEC bring-up ($MODE) ==="

say ""
say "--- 1. CEC hardware detected? ---"
if have cec-client; then
    cec-client -l 2>&1 | sed 's/^/  /'
else
    say "  cec-client missing (unexpected on LibreELEC)"
fi
if have cec-ctl; then
    say "  cec-ctl adapters: $(cec-ctl --list-devices 2>/dev/null | tr '\n' ' ')"
fi
say "  kernel cec devices: $(ls /dev/cec* 2>/dev/null || echo none)"

say ""
say "--- 2. USB devices (Pulse-Eight = 2548:1001/2548:1002, pico-cec = HID keyboard) ---"
if have lsusb; then
    lsusb 2>/dev/null | grep -iE "2548|pulse|seeed|raspberry|rp2|xia" | sed 's/^/  /' \
        || say "  no CEC-capable USB device found"
fi

say ""
say "--- 3. CEC adapter settings file ---"
CEC_XML=""
for f in "$PERIPH_DIR"/usb_2548_1002_CEC_Adapter.xml "$PERIPH_DIR"/usb_2548_1001_CEC_Adapter.xml; do
    [ -f "$f" ] && CEC_XML="$f" && break
done
if [ -n "$CEC_XML" ]; then
    say "  found: $CEC_XML"
    grep -E "device_type|activate_source|wake_devices|port|physical" "$CEC_XML" 2>/dev/null | sed 's/^/    /'
else
    say "  none yet ($PERIPH_DIR) - Kodi creates this once it sees a CEC adapter."
    say "  attach the adapter, start Kodi, then re-run this script."
fi

if [ "$MODE" = "apply" ]; then
    say ""
    say "--- 4. applying Vizio fix: device_type -> Playback ---"
    if [ -z "$CEC_XML" ]; then
        say "  ABORT: no CEC settings file yet; attach the adapter + let Kodi detect it first."
        exit 1
    fi
    mkdir -p "$BACKUP_DIR"
    cp "$CEC_XML" "$BACKUP_DIR/$(basename "$CEC_XML").bak.$(date +%Y%m%d-%H%M%S)" \
        && say "  backed up to $BACKUP_DIR"
    say "  stopping kodi (required, else the edit is discarded on exit)"
    systemctl stop kodi
    # Kodi 21 stores this enum as its label id, not the raw libCEC value:
    #   36051 = Recording Device (default, = libCEC 1)   <- what Vizio ignores
    #   36052 = Playback Device  (= libCEC 4)            <- the Vizio fix
    #   36053 = Tuner Device
    # (Kodi <=19 wrote the raw number 1/4/6 here instead; this box is 21.3.)
    if grep -q 'id="device_type"' "$CEC_XML"; then
        sed -i 's|\(id="device_type"[^>]*value="\)[^"]*"|\136052"|' "$CEC_XML"
    else
        sed -i 's|</settings>|    <setting id="device_type" value="36052"/>\n</settings>|' "$CEC_XML"
    fi
    grep -E "device_type" "$CEC_XML" | sed 's/^/    now: /'
    say "  starting kodi"
    systemctl start kodi
    say ""
    say "  Next: on the TV, power-cycle or toggle CEC off/on so it re-reads the device."
    say "  Then test a remote button and check: grep -i cec /storage/.kodi/temp/kodi.log"
    say "  If Vizio still ignores it, see the LE 12.2.x workarounds in docs/reference.md (delete the XML,"
    say "  try the TV's HDMI 1 / eARC port)."
fi

say ""
say "--- 4. Kodi log: CEC lines (last 10) ---"
grep -i cec /storage/.kodi/temp/kodi.log 2>/dev/null | tail -10 | sed 's/^/  /' || say "  none"
say ""
say "done."
