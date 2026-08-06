; Inno Setup script for Humanaize 2.0 Agent (ARM64)
; SourceDir 指向專案根目錄（installer\windows 的上兩層）

[Setup]
AppId={{HUMANAIZE2-ARM64-2024}}
AppName=Humanaize 2.0 Agent
AppVersion=2.3.0
AppVerName=Humanaize 2.0 Agent (ARM64) v2.3.0
AppPublisher=Humanaize Project
AppPublisherURL=https://github.com/A113NWu/Humanaize2-Project
AppSupportURL=https://github.com/A113NWu/Humanaize2-Project/issues
AppUpdatesURL=https://github.com/A113NWu/Humanaize2-Project/releases
DefaultDirName={autopf}\Humanaize2-arm64
DefaultGroupName=Humanaize 2.0 Agent
AllowNoIcons=yes
; 所有 Source 路徑相對於專案根目錄
SourceDir=..\..\
OutputDir=installer\windows\output
OutputBaseFilename=Humanaize2-Setup-arm64
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
PrivilegesRequired=admin
LicenseFile=docs\LICENSE
SetupIconFile=installer\windows\icon.ico
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add to PATH environment variable"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 主程式（PyInstaller onefile，自包含）
Source: "installer_output\arm64\Humanaize2-arm64.exe"; DestDir: "{app}"; Flags: ignoreversion
; Skills 目錄（可寫，供運行時安裝/更新技能）
Source: "skills\*"; DestDir: "{app}\skills"; Flags: ignoreversion recursesubdirs createallsubdirs
; 配置與運行時資料
Source: "config\version.json"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs
; 文檔
Source: "docs\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Humanaize 2.0 Agent (ARM64)"; Filename: "{app}\Humanaize2-arm64.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"
Name: "{group}\Uninstall Humanaize 2.0 Agent"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Humanaize 2.0 Agent (ARM64)"; Filename: "{app}\Humanaize2-arm64.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Humanaize2-arm64.exe"; Description: "{cm:LaunchProgram,Humanaize 2.0 Agent}"; Parameters: "boot -m gui"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Registry]
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
  if Pos(PathStr, s) > 0 then Exit;
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
    while Pos(';;', s) > 0 do
      Delete(s, Pos(';;', s), 1);
    RegWriteStringValue(HKEY_CURRENT_USER, REG_KEY, 'Path', s);
  end;
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
      SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, LPARAM(PChar('Environment')), SMTO_ABORTIFHUNG, 5000, nil);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppPath := ExpandConstant('{app}');
    RemoveFromPath(AppPath);
  end;
end;
