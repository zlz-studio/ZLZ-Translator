@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo === ZLZ Translator: ติดตั้งสำหรับรันจากซอร์ส (นักพัฒนา) ===
echo ผู้ใช้ทั่วไปไม่ต้องใช้ไฟล์นี้  โหลด Setup.exe จากหน้า Releases แทน
echo.

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>nul || (
  echo ไม่พบ Python  กรุณาติดตั้ง Python 3.11 ขึ้นไปจาก python.org ^(ติ๊ก "Add to PATH"^) แล้วรันไฟล์นี้ใหม่
  pause & exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo กำลังสร้าง virtual environment...
  %PY% -m venv .venv || (echo สร้าง .venv ไม่สำเร็จ & pause & exit /b 1)
)
echo กำลังติดตั้งไลบรารี...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || (echo ติดตั้งไลบรารีไม่สำเร็จ & pause & exit /b 1)

if not exist ".env" copy /y ".env.example" ".env" >nul

echo.
echo ติดตั้งเสร็จแล้ว  ตรวจสถานะผู้ให้บริการ:
".venv\Scripts\python.exe" -m core.cli status
echo.
echo ขั้นต่อไป: ดับเบิลคลิก dev\run.bat  (เปิดครั้งแรกจะมีตัวช่วยตั้งค่าทีละขั้นให้)
pause
