[Setup]
AppName=Dual Stream Audio Router
AppVersion=1.0.0
AppPublisher=Rishabh Jain
DefaultDirName={autopf}\Dual Stream
DefaultGroupName=Dual Stream
OutputDir=.\Output
OutputBaseFilename=DualStream_Setup_v1
Compression=lzma
SolidCompression=yes
SetupIconFile=compiler:SetupClassicIcon.ico
UninstallDisplayIcon={app}\ui_main.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\ui_main\ui_main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ui_main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Dual Stream"; Filename: "{app}\ui_main.exe"
Name: "{autodesktop}\Dual Stream"; Filename: "{app}\ui_main.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ui_main.exe"; Description: "Launch Dual Stream Audio Router"; Flags: nowait postinstall skipifsilent