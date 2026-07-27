#!/usr/bin/env bash
# Install the NORMA launcher + themed icon so the taskbar/dock shows the logo.
# The window icon comes from setWindowIcon(); the *taskbar* icon comes from the .desktop
# file + an icon installed in the hicolor theme, matched via StartupWMClass=norma-studio.
#
#   bash packaging/install_linux_desktop.sh           # install for the current user
#   bash packaging/install_linux_desktop.sh --uninstall
set -euo pipefail

APP_ID="norma-studio"
HERE="$(cd "$(dirname "$0")" && pwd)"
ASSETS="$HERE/../norma/studio/assets"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor"

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f "$APPS/$APP_ID.desktop" \
        "$ICONS/scalable/apps/$APP_ID.svg" \
        "$ICONS/256x256/apps/$APP_ID.png" \
        "$ICONS/512x512/apps/$APP_ID.png"
  echo "Removed NORMA desktop entry and icons."
else
  mkdir -p "$APPS" "$ICONS/scalable/apps" "$ICONS/256x256/apps" "$ICONS/512x512/apps"
  # scalable SVG (preferred by modern desktops) + PNG fallbacks
  install -m644 "$ASSETS/icon.svg"     "$ICONS/scalable/apps/$APP_ID.svg"
  install -m644 "$ASSETS/icon_256.png" "$ICONS/256x256/apps/$APP_ID.png"
  install -m644 "$ASSETS/icon_512.png" "$ICONS/512x512/apps/$APP_ID.png"

  # resolve the launcher's Exec to the installed entry point if it is on PATH
  EXEC="$(command -v norma-studio || echo norma-studio)"
  sed "s|^Exec=.*|Exec=$EXEC|" "$HERE/$APP_ID.desktop" > "$APPS/$APP_ID.desktop"
  chmod 644 "$APPS/$APP_ID.desktop"
  echo "Installed launcher: $APPS/$APP_ID.desktop"
fi

# refresh caches (best-effort; harmless if the tools are absent)
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v gtk-update-icon-cache  >/dev/null && gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
echo "Done. You may need to log out/in (or restart the shell) for the dock icon to refresh."
