# PyInstaller spec for norma studio  ->  standalone desktop executable.
# Build from the project root:  pyinstaller packaging/norma-studio.spec
import os, sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# numpy/scipy/sklearn/pandas produce a very deep import graph; PyInstaller's analysis
# recurses through it and hits Python's default recursion limit (-> RecursionError).
sys.setrecursionlimit(10000)

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))   # project root (importable `norma`)
ASSETS = os.path.join(ROOT, "norma", "studio", "assets")
ICO = os.path.join(ASSETS, "icon.ico")                 # Windows executable icon
ICNS = os.path.join(ASSETS, "icon.icns")               # macOS .app icon

# Rely on PyInstaller's built-in sklearn/scipy hooks (collecting *every* submodule can
# import network-linked extensions and clash with system libs); just pull in our package.
hiddenimports = collect_submodules("norma") + ["sklearn.isotonic", "scipy.special.cython_special"]

# Ship the brand assets so the runtime window icon (app_icon) resolves inside the bundle.
datas = collect_data_files("norma", includes=["studio/assets/*"])

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["torch", "matplotlib", "tkinter", "PyQt5", "PyQt6", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="norma-studio",
    console=False,                 # GUI app, no terminal window
    disable_windowed_traceback=False,
    icon=[ICO, ICNS],              # PyInstaller picks .ico on Windows, .icns on macOS
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name="norma-studio",           # -> dist/norma-studio/  (onedir bundle)
)

if sys.platform == "darwin":       # wrap into a proper macOS .app carrying the icns
    app = BUNDLE(
        coll,
        name="norma studio.app",
        icon=ICNS,
        bundle_identifier="org.normacpad.studio",
    )
