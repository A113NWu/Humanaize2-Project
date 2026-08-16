; Inno Setup script for Humanaize 2.0 Agent (x86_64)
; SourceDir 指向專案根目錄（installer\windows 的上兩層）

[Setup]
AppId={{HUMANAIZE2-X64-2024}}
AppName=Humanaize 2.0 Agent
AppVersion=2.2.6
AppVerName=Humanaize 2.0 Agent (x64) v2.2.6
AppPublisher=Humanaize Project
AppPublisherURL=https://github.com/A113NWu/Humanaize2-Project
AppSupportURL=https://github.com/A113NWu/Humanaize2-Project/issues
AppUpdatesURL=https://github.com/A113NWu/Humanaize2-Project/releases
DefaultDirName={autopf}\Humanaize2-x64
DefaultGroupName=Humanaize 2.0 Agent
AllowNoIcons=yes
; 所有 Source 路徑相對於專案根目錄
SourceDir=..\..\
OutputDir=installer\windows\output
OutputBaseFilename=Humanaize2-Setup-x86_64-v2.2.6
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
LicenseFile=docs\LICENSE
SetupIconFile=installer\windows\icon.ico
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add to PATH environment variable (use 'humanaize2' command anywhere)"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; 主程式（PyInstaller onefile，自包含）
Source: "installer_output\x86_64\Humanaize2-x86_64.exe"; DestDir: "{app}"; Flags: ignoreversion
; humanaize2 命令啟動腳本（讓用戶可在任意目錄使用 'humanaize2' 命令）
Source: "installer\windows\humanaize2.cmd"; DestDir: "{app}"; Flags: ignoreversion
; Skills 目錄（可寫，供運行時安裝/更新技能）
Source: "skills\*"; DestDir: "{app}\skills"; Flags: ignoreversion recursesubdirs createallsubdirs
; 配置與運行時資料
Source: "config\version.json"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs
; 文檔
Source: "docs\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Humanaize 2.0 Agent (x64)"; Filename: "{app}\Humanaize2-x86_64.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"
Name: "{group}\Uninstall Humanaize 2.0 Agent"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Humanaize 2.0 Agent (x64)"; Filename: "{app}\Humanaize2-x86_64.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Humanaize2-x86_64.exe"; Description: "{cm:LaunchProgram,Humanaize 2.0 Agent}"; Parameters: "boot -m gui"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Registry]
; 將安裝目錄加入系統 PATH（管理員安裝，使用 HKLM 讓所有用戶可用）
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}') and IsAdminInstallMode; Tasks: addtopath
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{app};{olddata}"; Check: NeedsAddPath('{app}') and not IsAdminInstallMode; Tasks: addtopath

[Code]
const
  HKLM_ENV_KEY = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  HKCU_ENV_KEY = 'Environment';
  SMTO_ABORTIFHUNG = $0002;

function SendMessageTimeout(hWnd: Longint; Msg: Longint; wParam: Longint; lParam: Longint; fuFlags: UINT; uTimeout: UINT; var lpdwResult: DWORD): LongBool;
  external 'SendMessageTimeoutW@user32.dll stdcall';

// 判斷指定路徑是否已存在於 PATH 變數中（用於 [Registry] Check）
// Param 為安裝目錄的展開值（{app}）
function NeedsAddPath(Param: string): boolean;
var
  PathStr: string;
begin
  Result := True;
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE, HKLM_ENV_KEY, 'Path', PathStr) then
  begin
    // HKLM 沒有 PATH，嘗試 HKCU
    if not RegQueryStringValue(HKEY_CURRENT_USER, HKCU_ENV_KEY, 'Path', PathStr) then
      Exit;
  end;
  // 檢查是否已包含（避免重複添加）
  if Pos(';' + Param + ';', ';' + PathStr + ';') > 0 then
    Result := False;
end;

// 從指定註冊表根鍵的 PATH 中移除指定路徑
procedure RemoveFromPathByKey(RootKey: Integer; SubKey: string; PathStr: string);
var
  s: string;
  p: Integer;
begin
  if not RegQueryStringValue(RootKey, SubKey, 'Path', s) then
    Exit;
  p := Pos(PathStr, s);
  if p > 0 then
  begin
    if p > 1 then
      Delete(s, p - 1, Length(PathStr) + 1)
    else
      Delete(s, p, Length(PathStr) + 1);
    while Pos(';;', s) > 0 do
      Delete(s, Pos(';;', s), 1);
    if s = '' then
      RegDeleteValue(RootKey, SubKey, 'Path')
    else
      RegWriteStringValue(RootKey, SubKey, 'Path', s);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppPath: string;
  dwResult: DWORD;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppPath := ExpandConstant('{app}');
    // 從 HKLM 和 HKCU 都嘗試移除（兼容不同安裝模式）
    RemoveFromPathByKey(HKEY_LOCAL_MACHINE, HKLM_ENV_KEY, AppPath);
    RemoveFromPathByKey(HKEY_CURRENT_USER, HKCU_ENV_KEY, AppPath);
    // 通知系統 PATH 已變更
    SendMessageTimeout($FFFF, $001A, 0, 0, SMTO_ABORTIFHUNG, 5000, dwResult);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  dwResult: DWORD;
begin
  // 安裝完成後廣播 WM_SETTINGCHANGE，讓新的 PATH 立即生效
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
  begin
    SendMessageTimeout($FFFF, $001A, 0, 0, SMTO_ABORTIFHUNG, 5000, dwResult);
  end;
end;
