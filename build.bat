@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === ZLZ Translator: สร้างตัวติดตั้ง ===

if not exist ".venv\Scripts\python.exe" (
  echo ยังไม่มี .venv  กรุณารัน setup.bat ก่อน
  pause & exit /b 1
)

set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install --quiet pyinstaller || (echo ติดตั้ง PyInstaller ไม่สำเร็จ & pause & exit /b 1)

for /f "usebackq delims=" %%v in (`"%PY%" -c "from core.config import APP_VERSION; print(APP_VERSION)"`) do set "VER=%%v"
echo เวอร์ชัน %VER%

echo [1/3] สร้างไอคอน
"%PY%" build\make_icon.py || (pause & exit /b 1)

echo [2/3] PyInstaller: อบโปรแกรม + Python เป็นโฟลเดอร์ dist\ZLZ Translator
if exist "dist\ZLZ Translator" rmdir /s /q "dist\ZLZ Translator"
"%PY%" -m PyInstaller --noconfirm --clean --workpath build\pyi --distpath dist zlz_translator.spec || (echo PyInstaller ล้มเหลว & pause & exit /b 1)

echo [3/3] Inno Setup: ห่อเป็น Setup.exe
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo ไม่พบ Inno Setup  ติดตั้งด้วย:  winget install JRSoftware.InnoSetup
  echo ตัวโปรแกรมแบบไม่มีตัวติดตั้งอยู่ที่ dist\ZLZ Translator\ZLZ Translator.exe
  pause & exit /b 1
)
"%ISCC%" /Q "/DMyAppVersion=%VER%" installer\ZLZ-Translator.iss || (echo Inno Setup ล้มเหลว & pause & exit /b 1)

echo.
echo เสร็จแล้ว:  dist\ZLZ-Translator-Setup-%VER%.exe
echo อัปโหลดไฟล์นี้ขึ้น GitHub Releases เพื่อแจกให้คนอื่น
pause
