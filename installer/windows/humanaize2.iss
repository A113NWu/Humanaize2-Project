; Inno Setup Script for Humanaize 2.0 Agent
; Generated for Windows Installer

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EFGHIJKLMNOP}
AppName=Humanaize 2.0 Agent
AppVersion=2.2.3
AppPublisher=Humanaize Project
AppPublisherURL=https://github.com/A113NWu/Humanaize2-Project
AppSupportURL=https://github.com/A113NWu/Humanaize2-Project/issues
AppUpdatesURL=https://github.com/A113NWu/Humanaize2-Project/releases
DefaultDirName={autopf}\Humanaize 2.0 Agent
DefaultGroupName=Humanaize 2.0 Agent
AllowNoIcons=no
LicenseFile=..\..\LICENSE
OutputDir=installer_output
OutputBaseFilename=Humanaize2-Setup-v2.1.0
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile=icon.ico
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "addtopath"; Description: "Add to PATH environment variable"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable (PyInstaller bundled exe)
Source: "Humanaize2.exe"; DestDir: "{app}"; Flags: ignoreversion

; Command-line launcher script
Source: "..\..\humanaize2.bat"; DestDir: "{app}"; Flags: ignoreversion

; Skills directory
Source: "..\..\skills\*"; DestDir: "{app}\skills"; Flags: ignoreversion recursesubdirs createallsubdirs

; Configuration files
Source: "..\..\version.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion

; Data directory (empty, for runtime data)
Source: "..\..\data\.gitkeep"; DestDir: "{app}\data"; Flags: ignoreversion

[Icons]
Name: "{group}\Humanaize 2.0 Agent"; Filename: "{app}\Humanaize2.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"
Name: "{group}\Uninstall Humanaize 2.0 Agent"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Humanaize 2.0 Agent"; Filename: "{app}\Humanaize2.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Humanaize2.exe"; Description: "{cm:LaunchProgram,Humanaize 2.0 Agent}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Registry]
; Add Humanaize2 to user PATH
; This creates a new PATH entry specifically for Humanaize2
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "Humanaize2Path"; ValueData: "{app}"; Flags: uninsdeletevalue; Tasks: addtopath

[Code]
const
  REG_KEY = 'Environment';

function GetUserPath(): string;
var
  s: string;
begin
  Result := '';
  if RegQueryStringValue(HKEY_CURRENT_USER, REG_KEY, 'Path', s) then
    Result := s;
end;

procedure AddToPath(PathStr: string);
var
  s: string;
begin
  s := GetUserPath();
  if s <> '' then
    s := s + ';' + PathStr
  else
    s := PathStr;
  RegWriteStringValue(HKEY_CURRENT_USER, REG_KEY, 'Path', s);
end;

procedure RemoveFromPath(PathStr: string);
var
  s: string;
  p: Integer;
begin
  s := GetUserPath();
  p := Pos(PathStr, s);
  if p > 0 then
  begin
    if p > 1 then
      Delete(s, p - 1, Length(PathStr) + 1)
    else
      Delete(s, p, Length(PathStr) + 1);
    // Clean up leading/trailing semicolons
    while Pos(';;', s) > 0 do
      Delete(s, Pos(';;', s), 1);
    RegWriteStringValue(HKEY_CURRENT_USER, REG_KEY, 'Path', s);
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    if IsTaskSelected('addtopath') then
    begin
      AppPath := ExpandConstant('{app}');
      AddToPath(AppPath);
      
      // Broadcast environment change
      SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, LPARAM(PChar('Environment')), SMTO_ABORTIFHUNG, 5000, nil);
    end;
  end;
end;