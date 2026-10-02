@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo === ZLZ Translator: อัปเดตซอร์สเป็นเวอร์ชันล่าสุด (นักพัฒนา) ===
echo ผู้ใช้ทั่วไป: โหลด Setup.exe ตัวใหม่จากหน้า Releases แล้วรันทับได้เลย
echo.

if exist ".git" (
  where git >nul 2>nul || (
    echo ไม่พบ git ในเครื่อง  ให้โหลด zip ใหม่จาก GitHub ^(Code ^> Download ZIP^) มาแตกทับแทน
    pause & exit /b 1
  )
  echo กำลังดึงโค้ดล่าสุดจาก GitHub...
  git pull --ff-only || (
    echo ดึงโค้ดไม่สำเร็จ  ถ้าเคยแก้ไฟล์เอง ให้เก็บสำเนาไว้แล้วโหลด zip ใหม่มาแตกทับ
    pause & exit /b 1
  )
) else (
  echo โฟลเดอร์นี้ไม่ได้มาจาก git clone  ให้โหลด zip ใหม่จาก GitHub มาแตกทับโฟลเดอร์นี้
  echo ^(ไฟล์ .env และ glossary.md ของคุณจะไม่ถูกทับ เพราะไม่อยู่ใน zip^)
  pause & exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
  echo ยังไม่เคยติดตั้ง  กำลังเรียก dev\setup.bat...
  call "dev\setup.bat"
  exit /b
)
echo กำลังอัปเดตไลบรารี...
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

echo.
echo อัปเดตเสร็จแล้ว  ถ้าโปรแกรมเปิดอยู่ ให้คลิกขวาไอคอน tray เลือก "ออกจากโปรแกรม" แล้วเปิด dev\run.bat ใหม่
pause
