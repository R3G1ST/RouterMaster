[Setup]
AppId={{8E7F2B1C-9A3D-4F5E-8B2A-0C1D2E3F4A5B}
AppName=RouterMaster
AppVersion=1.5.0
AppPublisher=RouterMaster
DefaultDirName={autopf}\RouterMaster
DefaultGroupName=RouterMaster
UninstallDisplayIcon={app}\RouterMaster.exe
OutputDir=C:\Users\R3G1S\OneDrive\Документы\Default Project Redesign\installer
OutputBaseFilename=RouterMaster-Setup
SetupIconFile=C:\Users\R3G1S\OneDrive\Документы\Default Project Redesign\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
CloseApplicationsFilter=RouterMaster.exe,RouterMasterAdmin.exe

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: checkedonce

[Files]
Source: "C:\Users\R3G1S\OneDrive\Документы\Default Project Redesign\dist\RouterMaster.exe"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\RouterMaster.exe"; Description: "Запустить RouterMaster"; Flags: nowait postinstall

[Icons]
Name: "{autoprograms}\RouterMaster"; Filename: "{app}\RouterMaster.exe"; IconFilename: "{app}\RouterMaster.exe"
Name: "{autodesktop}\RouterMaster"; Filename: "{app}\RouterMaster.exe"; IconFilename: "{app}\RouterMaster.exe"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\RouterMaster"

[Code]
procedure KillProcesses;
var
  Locator, WMIService, Items, Item: Variant;
  i: Integer;
begin
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    WMIService := Locator.ConnectServer('.', 'root\cimv2');
    Items := WMIService.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''RouterMaster.exe'' OR Name = ''RouterMasterAdmin.exe''');
    for i := 0 to Items.Count - 1 do
    begin
      Item := Items.ItemIndex(i);
      Item.Terminate();
    end;
    Sleep(500);
    for i := 1 to 10 do
    begin
      Items := WMIService.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''RouterMaster.exe'' OR Name = ''RouterMasterAdmin.exe''');
      if Items.Count = 0 then
        break;
      Sleep(500);
    end;
  except
  end;
end;

function InitializeSetup(): Boolean;
begin
  KillProcesses;
  Result := True;
end;