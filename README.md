# ZLZ Translator

Repo: https://github.com/zlz-studio/ZLZ-Translator
มือใหม่เริ่มที่ **[FRIEND_GUIDE.md](FRIEND_GUIDE.md)** (ติดตั้งใน 5 นาที ใช้แค่บัญชี Gmail)

## ติดตั้ง (แบบง่าย ไม่ต้องลง Python)

1. โหลด **`ZLZ-Translator-Setup-x.y.z.exe`** จากหน้า [Releases](https://github.com/zlz-studio/ZLZ-Translator/releases) แล้วดับเบิลคลิก
2. กด Next จนเสร็จ (ติดตั้งในโฟลเดอร์ผู้ใช้ ไม่ต้องสิทธิ์ Admin ได้ไอคอนบน Desktop + Start Menu + ตัว Uninstall)
3. เปิดโปรแกรมครั้งแรกจะเจอ **ตัวช่วยตั้งค่าทีละขั้น**: ตรวจ/ติดตั้ง Claude Code ให้ → ปุ่มพาไปขอคีย์ Gemini แล้วตรวจคีย์ให้ → ปุ่ม Login Claude → เสร็จ กด "ถัดไป" ไม่ได้จนกว่าแต่ละขั้นจะผ่านจริง
4. โปรแกรมไปอยู่ที่ไอคอนมุมขวาล่างจอ กด **F8** / **F9** ได้เลย

ข้อมูลของคุณ (คีย์, config.toml, glossary.md, log) เก็บที่ `%APPDATA%\ZLZ Translator` ไม่ได้อยู่ในโฟลเดอร์โปรแกรม อัปเดตเวอร์ชันใหม่โดยรัน Setup.exe ตัวใหม่ทับได้เลย ค่าที่ตั้งไว้ไม่หาย
เรียกตัวช่วยตั้งค่าซ้ำได้จากเมนูไอคอน tray > **ตัวช่วยตั้งค่าทีละขั้น...**

เครื่องมือแปลสำหรับฟรีแลนซ์ไทยที่ต้องคุยกับลูกค้าต่างชาติ ใช้ได้กับ Discord และทุกแอปบน Windows
แปลผ่าน **Claude Code** (ใช้โควต้าสมาชิก Claude ที่มีอยู่ ไม่ต้องเติมเครดิต) และสลับไป Gemini / Claude API / Ollama ได้

## ทำอะไรได้

| ปุ่มลัด | ทำอะไร |
|---|---|
| **F8** | ลากคลุมข้อความอังกฤษของลูกค้า -> ป๊อปอัปแปลไทย |
| **F9** | พิมพ์ไทยในช่องแชท -> ข้อความถูกแทนที่ด้วยอังกฤษ **ยังไม่ส่ง** อ่านก่อนแล้วค่อยกด Enter |
| **Shift+F8** | ลากคลุมข้อความอังกฤษ -> อธิบายเป็นไทยว่าลูกค้าหมายถึงอะไร ต้องการอะไร น้ำเสียงเป็นยังไง |
| **Shift+F9** | พิมพ์อังกฤษเองในช่องแชท -> แก้ไวยากรณ์ให้ถูกและเป็นธรรมชาติ |

ในป๊อปอัปมีปุ่ม **ก๊อป**, เปลี่ยนน้ำเสียง (**ทางการ / เป็นกันเอง / สั้น**) และ **แปลกลับเช็ก** เพื่อดูว่าอังกฤษที่ได้ตรงกับที่ตั้งใจไหม

**ไอคอนที่ system tray (มุมขวาล่าง)**
- คลิกซ้าย = เปิด/ปิดการทำงานชั่วคราว (สีเทา = ปิด, สีส้ม = กำลังแปล)
- คลิกขวา = เมนู: **ตั้งค่าคีย์และบัญชี...** (ปุ่มพาไปหน้าขอคีย์ Gemini, ช่องวางคีย์, **ตั้งปุ่มลัดเองโดยกดคีย์ที่ต้องการ**, ตัวเลือกให้ปุ่มลัดทำงานเฉพาะใน Discord), น้ำเสียงตอนตอบ, เปิด/ปิด Discord app, **เปิดอัตโนมัติเมื่อเข้า Windows**, คลังศัพท์, จำนวนครั้งที่ใช้วันนี้, ออกจากโปรแกรม
- ปุ่มลัดทำงานได้ทุกโปรแกรม ไม่เฉพาะ Discord

> ส่งให้คนอื่นใช้: ส่งลิงก์หน้า [Releases](https://github.com/zlz-studio/ZLZ-Translator/releases) ให้โหลด Setup.exe (ไม่มีคีย์ของคุณติดไปแน่นอน เพราะคีย์อยู่ใน `%APPDATA%` ไม่ได้อยู่ในตัวโปรแกรม)

> ขั้นตอนแบบละเอียดทีละคลิก อยู่ใน **[SETUP_GUIDE.md](SETUP_GUIDE.md)**

## สร้างตัวติดตั้งเอง (สำหรับผู้พัฒนา)

- **ในเครื่อง**: ดับเบิลคลิก `build.bat` (ต้องมี `.venv` จาก `setup.bat` และ [Inno Setup 6](https://jrsoftware.org/isinfo.php) — ลงด้วย `winget install JRSoftware.InnoSetup`) ได้ `dist\ZLZ-Translator-Setup-<เวอร์ชัน>.exe`
- **อัตโนมัติบน GitHub**: แก้ `APP_VERSION` ใน `core/config.py` แล้ว `git tag v1.0.1 && git push origin v1.0.1` → GitHub Actions (`.github/workflows/release.yml`) จะ build และแนบ Setup.exe ขึ้นหน้า Releases ให้เอง
- ส่วนประกอบ: `zlz_translator.py` (จุดเข้าโปรแกรม), `zlz_translator.spec` (PyInstaller), `installer/ZLZ-Translator.iss` (Inno Setup), `build/make_icon.py` (ไอคอน)

## ติดตั้งจากซอร์สโค้ด (สำหรับผู้พัฒนา ทำครั้งเดียว)

**1. ติดตั้งไลบรารี** ดับเบิลคลิก `setup.bat` (ต้องมี Python 3.11 ขึ้นไป ถ้ายังไม่มีโหลดจาก python.org แล้วติ๊ก "Add to PATH")

**2. ล็อกอิน Claude Code หนึ่งครั้ง** เลือกทางใดทางหนึ่ง

- *ทาง ก: ใช้ไบนารีที่มากับแอป Claude Desktop* (บนเครื่องนี้ทำแล้ว) เปิด PowerShell แล้วรัน

  ```powershell
  & "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\2.1.280\claude.exe" auth login --claudeai
  ```

  กด Authorize ในเบราว์เซอร์ที่เด้งขึ้น (แอป Claude แบบ Store package เก็บไบนารีไว้ใต้ `AppData\Local\Packages` ดูรายละเอียดใน SETUP_GUIDE.md ขั้นที่ 1)

- *ทาง ข: ติดตั้ง Claude Code CLI แบบทางการ* รันใน PowerShell

  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```

  จากนั้นรัน `claude` แล้วพิมพ์ `/login`

**3. ตรวจว่าพร้อม** รันใน PowerShell ที่โฟลเดอร์นี้

```powershell
.venv\Scripts\python.exe -m core.cli read "Could you send me the updated files by Friday?"
```

ถ้าได้คำแปลไทยกลับมา แปลว่าใช้ได้แล้ว

**4. (ทางเลือก) ใส่คีย์สำรอง** เปิดไฟล์ `.env` แล้วใส่ `GEMINI_API_KEY=...` (ขอฟรีที่ aistudio.google.com/apikey) เผื่อวันไหนโควต้า Claude ชนเพดาน โปรแกรมจะสลับไปใช้ให้เอง

## ใช้งานประจำวัน

ดับเบิลคลิก `run_hotkey.bat` โปรแกรมจะไปอยู่ที่ system tray แล้วใช้ปุ่มลัดได้ทันทีในทุกแอป
ถ้าอยากให้เปิดเองตอนเข้า Windows: กด Win+R พิมพ์ `shell:startup` แล้วสร้าง shortcut ของ `run_hotkey.bat` ไว้ในนั้น

## ปรับแต่ง

- **`glossary.md`** ใส่ชื่อโปรเจกต์ ศัพท์ที่ห้ามแปล และแนวทางน้ำเสียง ยิ่งละเอียดยิ่งแปลตรง (แก้แล้วเลือก "โหลดการตั้งค่าใหม่" ที่ tray)
- **`config.toml`**
  - `provider_order` ลำดับผู้ให้บริการ ตัวแรกคือหลัก ที่เหลือคือสำรอง
  - `[modes]` รุ่นโมเดลต่อโหมด `haiku` เร็วและประหยัดโควต้าที่สุด `sonnet` สมดุล `opus` ดีที่สุดแต่กินโควต้ามาก
  - `[hotkeys]` เปลี่ยนปุ่มลัดได้ถ้าชนกับโปรแกรมอื่น
  - `default_tone` น้ำเสียงเริ่มต้นตอนตอบ

## ทดสอบจาก command line

```powershell
.venv\Scripts\python.exe -m core.cli status
.venv\Scripts\python.exe -m core.cli reply "น่าจะส่งให้ได้พรุ่งนี้เช้าครับ" --tone formal
.venv\Scripts\python.exe -m core.cli explain "Can we circle back on this next sprint?" --provider gemini
.venv\Scripts\python.exe tests\test_core.py
```

## แก้ปัญหา

| อาการ | วิธีแก้ |
|---|---|
| ป๊อปอัปแดงบอก "ยังไม่ได้ล็อกอิน" | ทำข้อ 2 ในการติดตั้ง |
| "ไม่พบ Claude Code CLI" | ระบุพาธเองใน `config.toml` ที่ `providers.claude_code.command` |
| กดปุ่มลัดแล้วไม่มีอะไรเกิดขึ้น | เช็กว่าโปรแกรมรันอยู่ (มีไอคอนที่ tray) และปุ่มลัดไม่ชนกับแอปอื่น |
| F9 แทนที่ข้อความผิดช่อง | ต้องคลิกให้เคอร์เซอร์อยู่ในช่องพิมพ์ก่อนกด ปุ่มนี้ใช้ "เลือกทั้งหมด" ในช่องที่โฟกัสอยู่ |
| ช้า | ตั้ง `[modes]` ให้ใช้ `haiku` หรือลด `effort` |
| ดู log | `data\hotkey.log` |

## ข้อควรรู้

- ทุกการแปลผ่าน Claude Code จะกินโควต้าสมาชิกเล็กน้อย ดูจำนวนครั้งต่อวันได้ที่เมนู tray
- ข้อความจะถูกส่งไปยังผู้ให้บริการที่เลือกเท่านั้น ไม่มีการเก็บไว้ที่อื่น (ยกเว้น log ในเครื่องซึ่งไม่เก็บเนื้อหาข้อความ)
- ไฟล์ `.env` เป็นความลับ อย่าแชร์

## Discord User App (คลิกขวาแปลได้ในตัว Discord)

ติดตั้งที่ "ตัวคุณ" ไม่ใช่ที่เซิร์ฟเวอร์ จึงใช้ได้ทุกเซิร์ฟเวอร์ของลูกค้าและใน DM โดยไม่ต้องขอสิทธิ์ใคร ผลลัพธ์เห็นเฉพาะคุณ ใช้จากมือถือได้ตราบใดที่ PC ยังเปิดโปรแกรมอยู่

| ที่ไหน | ทำอะไร |
|---|---|
| คลิกขวาที่ข้อความ -> **Apps -> แปลเป็นไทย** | แปลข้อความนั้นเป็นไทย |
| คลิกขวาที่ข้อความ -> **Apps -> อธิบายข้อความนี้** | สรุปว่าลูกค้าหมายถึงอะไร ต้องการอะไร น้ำเสียงยังไง |
| `/en ข้อความไทย` | ร่างอังกฤษ + แปลกลับให้เช็ก แล้วก๊อปไปวางในช่องพิมพ์ส่งเอง (ขึ้นเป็นชื่อคุณ) |
| `/th ข้อความอังกฤษ` | แปลเป็นไทย |
| `/fix ข้อความอังกฤษ` | แก้อังกฤษที่พิมพ์เองให้ถูก |

บนมือถือ: กดค้างที่ข้อความ -> Apps
แอปนี้ **ไม่โพสต์อะไรลงแชทเอง** ทุกผลลัพธ์เห็นเฉพาะคุณ ข้อความที่ส่งจริงต้องมาจากช่องพิมพ์ของคุณเสมอ จึงขึ้นเป็นชื่อคุณ

### ตั้งค่าครั้งแรก (ประมาณ 5 นาที)

1. เข้า https://discord.com/developers/applications กด **New Application** ตั้งชื่อเช่น `Translator` แล้ว Create
2. เมนูซ้าย **Installation**
   - Installation Contexts: ติ๊ก **User Install** (ติ๊ก Guild Install ด้วยก็ได้)
   - Install Link: เลือก **Discord Provided Link**
   - กด Save Changes แล้วก๊อปลิงก์ Install Link เก็บไว้
3. เมนูซ้าย **Bot** กด **Reset Token** ก๊อป token มาใส่ในไฟล์ `.env` บรรทัด `DISCORD_TOKEN=...` (token เป็นความลับ ห้ามแชร์)
4. เปิดลิงก์ Install Link ในเบราว์เซอร์ เลือก **Add to My Apps** แล้ว Authorize
5. ดับเบิลคลิก `run_hotkey.bat` โปรแกรม Hotkey จะเปิด Discord app ให้เองเมื่อพบ DISCORD_TOKEN (เปิด/ปิดได้ที่เมนูไอคอน tray) ไม่มีหน้าต่างค้าง
6. ใน Discord ลองพิมพ์ `/en` ถ้ายังไม่ขึ้น กด Ctrl+R ใน Discord เพื่อรีโหลด

`run_discord.bat` มีไว้เฉพาะกรณีอยากรัน Discord app เดี่ยวๆ พร้อมดู log ในหน้าต่าง
