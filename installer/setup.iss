[Setup]
AppId={{8E7F2B1C-9A3D-4F5E-8B2A-0C1D2E3F4A5B}
AppName=RouterMaster
AppVersion=1.4.1
AppPublisher=RouterMaster
DefaultDirName={autopf}\RouterMaster
DefaultGroupName=RouterMaster
UninstallDisplayIcon={app}\RouterMaster.exe
OutputDir=C:\Users\R3G1S\OneDrive\Документы\Default Project\installer
OutputBaseFilename=RouterMaster-Setup
SetupIconFile=C:\Users\R3G1S\OneDrive\Документы\Default Project\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: checkedonce

[Files]
Source: "C:\Users\R3G1S\OneDrive\Документы\Default Project\dist\RouterMaster.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RouterMaster"; Filename: "{app}\RouterMaster.exe"; IconFilename: "{app}\RouterMaster.exe"
Name: "{autodesktop}\RouterMaster"; Filename: "{app}\RouterMaster.exe"; IconFilename: "{app}\RouterMaster.exe"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\RouterMaster"