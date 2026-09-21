#!/bin/sh
# Install Arctic Fuse 3 (jurialmunkey) + dependencies on a LibreELEC box,
# side-by-side with the existing skin. The skin is installed DISABLED: switch
# it at the TV (Settings -> Interface -> Skin), where its setup wizard runs.
#
# Run ON the box:  sh /storage/install-arctic-fuse3.sh
# (needs curl + unzip, both present in LibreELEC)
set -u

DEST=/storage/.kodi/addons
TMP=/storage/af3-install
JMC=https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/omega/zips
KODI=https://mirrors.kodi.tv/addons/omega
mkdir -p "$TMP"

fetch_install() {
  url="$1"
  f="$TMP/$(basename "$url")"
  i=1
  while [ "$i" -le 4 ]; do
    if curl -sL --max-time 150 "$url" -o "$f" && [ -s "$f" ] && unzip -q -o "$f" -d "$DEST"; then
      echo "ok: $(basename "$url")"
      return 0
    fi
    echo "retry $i: $(basename "$url")"
    i=$((i + 1))
    sleep 4
  done
  echo "FAILED: $url"
  return 1
}

# Repository, so Kodi can update these addons itself later
fetch_install https://jurialmunkey.github.io/repository.jurialmunkey/repository.jurialmunkey-3.4.zip

# Skin + declared dependencies
fetch_install "$JMC/skin.arctic.fuse.3/skin.arctic.fuse.3-3.3.1.zip"
fetch_install "$JMC/script.skinvariables/script.skinvariables-2.2.4.zip"
fetch_install "$JMC/script.texturemaker/script.texturemaker-0.2.11.zip"
fetch_install "$JMC/plugin.video.themoviedb.helper/plugin.video.themoviedb.helper-6.17.3.zip"
fetch_install "$JMC/script.module.jurialmunkey/script.module.jurialmunkey-0.2.35.zip"
fetch_install "$JMC/script.module.infotagger/script.module.infotagger-0.0.9.zip"
fetch_install "$JMC/resource.font.robotocjksc/resource.font.robotocjksc-0.0.3.zip"

# Dependencies served by the official Kodi repo
fetch_install "$KODI/script.module.addon.signals/script.module.addon.signals-0.0.6+matrix.1.zip"
fetch_install "$KODI/script.module.qrcode/script.module.qrcode-6.1.0+matrix.3.zip"
fetch_install "$KODI/resource.images.weathericons.white/resource.images.weathericons.white-0.0.6.zip"
fetch_install "$KODI/resource.images.studios.coloured/resource.images.studios.coloured-0.0.24.zip"

# The font addon's zip unpacks to a misspelled folder; the skin requires the
# correctly spelled addon id, so fix it or the dependency stays unmet.
if [ -d "$DEST/resource.font.robotcjksc" ] && [ ! -d "$DEST/resource.font.robotocjksc" ]; then
  mv "$DEST/resource.font.robotcjksc" "$DEST/resource.font.robotocjksc"
  echo "fixed: resource.font.robotocjksc (upstream zip folder typo)"
fi

echo "--- verify ---"
missing=0
for a in skin.arctic.fuse.3 repository.jurialmunkey script.skinvariables script.texturemaker \
         plugin.video.themoviedb.helper script.module.jurialmunkey script.module.infotagger \
         resource.font.robotocjksc script.module.addon.signals script.module.qrcode \
         resource.images.weathericons.white resource.images.studios.coloured; do
  if [ -f "$DEST/$a/addon.xml" ]; then
    printf '  OK   %s\n' "$a"
  else
    printf '  MISS %s\n' "$a"
    missing=$((missing + 1))
  fi
done
rm -rf "$TMP"
echo "missing: $missing"
echo "Next: restart Kodi so it rescans addons, then enable the helper addons"
echo "(script.skinvariables, script.texturemaker, plugin.video.themoviedb.helper)"
echo "and switch the skin at the TV: Settings -> Interface -> Skin -> Arctic Fuse 3"
