#!/usr/bin/env bash
# Build a standalone Linux executable, then (optionally) an AppImage.
# Run from the project root:  bash packaging/build_linux.sh
set -e
cd "$(dirname "$0")/.."

pip install --quiet pyinstaller

# PyInstaller assembles the bundle with symlinks, which fail on mounted drives
# (exFAT/NTFS). Build on a local filesystem, then rsync -L (dereference) into ./dist so
# the final bundle is symlink-free and runs from anywhere.
TMP="${TMPDIR:-/tmp}/norma_build_$$"
mkdir -p "$TMP"

# Conda environments sometimes ship an inconsistent krb5 family; preload the system one
# so PyInstaller's analysis can import OpenSSL-linked modules. Harmless elsewhere.
PRE=""
for L in libkrb5support.so.0 libcom_err.so.3 libk5crypto.so.3 libkrb5.so.3 libgssapi_krb5.so.2; do
  [ -e "/lib/x86_64-linux-gnu/$L" ] && PRE="$PRE/lib/x86_64-linux-gnu/$L:"
done

LD_PRELOAD="$PRE" pyinstaller --noconfirm \
  --distpath "$TMP/dist" --workpath "$TMP/build" packaging/norma-studio.spec

rm -rf dist/norma-studio; mkdir -p dist
rsync -aL "$TMP/dist/norma-studio" dist/
rm -rf "$TMP"
echo "Executable: dist/norma-studio/norma-studio"

# --- optional: wrap dist/norma-studio into a portable AppImage ------------------
if command -v appimagetool >/dev/null 2>&1; then
  APP=dist/AppDir; rm -rf "$APP"; mkdir -p "$APP/usr/bin"
  cp -rL dist/norma-studio/* "$APP/usr/bin/"
  cat > "$APP/norma-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=norma studio
Exec=norma-studio
Icon=norma-studio
Categories=Development;Database;
EOF
  ln -sf usr/bin/norma-studio "$APP/AppRun"
  appimagetool "$APP" dist/norma-studio.AppImage && echo "AppImage: dist/norma-studio.AppImage"
else
  echo "appimagetool introuvable : binaire onedir pret dans dist/norma-studio/."
fi
