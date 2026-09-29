; สคริปต์ Inno Setup: ห่อ dist\ZLZ Translator\ เป็น Setup.exe ติดตั้งแบบต่อผู้ใช้ (ไม่ต้อง Admin)
; build.bat เรียกให้เอง:  ISCC.exe /DMyAppVersion=1.0.0 installer\ZLZ-Translator.iss

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "ZLZ Translator"
#define MyAppPublisher "ZLZ Studio"
#define MyAppURL "https://github.com/zlz-studio/ZLZ-Translator"
#define MyAppExeName "ZLZ Translator.exe"

[Setup]
AppId={{8F3E2A1C-5B7D-4E6F-9A0B-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
; ติดตั้งในโฟลเดอร์ผู้ใช้ -> ไม่ต้องสิทธิ์ Admin และ Claude/Gemini ก็เป็นบัญชีต่อผู้ใช้อยู่แล้ว
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ZLZ-Translator-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; ถ้าโปรแกรมเปิดอยู่ ให้ตัวติดตั้งขอปิดก่อน (ตอนอัปเดตทับ)
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; ติดตั้งเสร็จเปิดโปรแกรมทันที (ครั้งแรกจะเจอตัวช่วยตั้งค่าทีละขั้น)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; ลบ shortcut เปิดอัตโนมัติที่โปรแกรมสร้างไว้ในโฟลเดอร์ Startup (ข้อมูลผู้ใช้ใน %APPDATA% เก็บไว้)
Type: files; Name: "{userstartup}\{#MyAppName}.lnk"
