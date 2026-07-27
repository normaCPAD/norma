@echo off
REM Build a standalone Windows executable (.exe). Run from the project root:
REM     packaging\build_windows.bat
cd /d "%~dp0\.."
pip install pyinstaller
pyinstaller --noconfirm packaging\norma-studio.spec
echo Executable: dist\norma-studio\norma-studio.exe
REM For a single-file installer, post-process dist\norma-studio with Inno Setup or NSIS.
