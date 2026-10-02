@echo off
cd /d "%~dp0.."
if not exist ".venv\Scripts\pythonw.exe" (
  echo ยังไม่ได้ติดตั้ง  กรุณาดับเบิลคลิก dev\setup.bat ก่อน
  pause & exit /b 1
)
rem เปิดโปรแกรมจากซอร์ส (pythonw = ไม่มีหน้าต่างดำค้าง)  โปรแกรมจะไปอยู่ที่ system tray
rem ครั้งแรกจะเจอตัวช่วยตั้งค่าทีละขั้น  และจะเปิด Discord app ให้เองถ้ามี DISCORD_TOKEN ใน .env
start "" ".venv\Scripts\pythonw.exe" "dev\zlz_translator.py"
