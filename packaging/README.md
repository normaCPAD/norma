# Packaging norma studio as a standalone executable

The app is bundled with **PyInstaller** (one folder containing the executable and all
dependencies, including the Qt runtime and the SQLite driver). No Python install is then
needed on the target machine.

## Linux (executable + AppImage)

```bash
bash packaging/build_linux.sh
# -> dist/norma-studio/norma-studio          (run directly)
# -> dist/norma-studio.AppImage              (if appimagetool is installed)
```

For the AppImage, install
[appimagetool](https://github.com/AppImage/AppImageKit/releases) and re-run the script;
replace the placeholder icon with a real PNG for production.

## Windows (.exe)

```bat
packaging\build_windows.bat
REM -> dist\norma-studio\norma-studio.exe
```

Wrap `dist\norma-studio\` with **Inno Setup** or **NSIS** to get a single-file installer.

## macOS (.app)

```bash
pyinstaller --noconfirm --windowed packaging/norma-studio.spec
# -> dist/norma-studio.app
```

## Notes
- `torch` is excluded (the desktop app uses the non-neural CPAD variants); the optional
  GatedCPAD model is not bundled.
- If a constraint solver or a database driver is missing at runtime, add it to
  `hiddenimports` in `norma-studio.spec`.

## Troubleshooting (already handled by `build_linux.sh`)
- **`os.symlink ... Operation not permitted`** : the project lives on a mounted drive
  (exFAT/NTFS) that has no symlinks. The script builds on a local filesystem and copies
  the result with `rsync -L`, so the final `dist/` is symlink-free.
- **`libgssapi_krb5.so.2: undefined symbol k5_buf_cstring`** (conda envs) : the conda
  krb5 family is inconsistent with the system one. The script preloads the system krb5
  libraries for the build; alternatively run `conda install -c conda-forge krb5` or build
  in a plain `python -m venv`.
- The verified build produced a 34 MB executable (711 MB bundle) that launches cleanly.
