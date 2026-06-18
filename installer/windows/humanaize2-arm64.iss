; Inno Setup script for Humanaize 2.0 Agent (ARM64)
; Generated for Windows ARM64 architecture

[Setup]
AppId={{HUMANAIZE2-ARM64-2024}}
AppName=Humanaize 2.0 Agent
AppVersion=2.2.3
AppVerName=Humanaize 2.0 Agent (ARM64)
AppPublisher=Humanaize Team
AppPublisherURL=https://github.com/humanaize
AppSupportURL=https://github.com/humanaize/humanaize2/issues
AppUpdatesURL=https://github.com/humanaize/humanaize2
DefaultDirName={autopf}\Humanaize2-arm64
DefaultGroupName=Humanaize 2.0 Agent
AllowNoIcons=yes
LicenseFile=..\docs\LICENSE
InfoBeforeFile=..\docs\README.md
OutputDir=output
OutputBaseFilename=Humanaize2-Setup-arm64
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinese"; MessagesFile: "compiler:ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "installer_output/arm64/Humanaize2-arm64.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\ui\ascii.txt"; DestDir: "{app}\src\ui"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "src\config\*.py"; DestDir: "{app}\src\config"; Flags: ignoreversion
Source: "src\core\*.py"; DestDir: "{app}\src\core"; Flags: ignoreversion
Source: "src\ui\*.py"; DestDir: "{app}\src\ui"; Flags: ignoreversion
Source: "src\llm\*.py"; DestDir: "{app}\src\llm"; Flags: ignoreversion
Source: "src\memory\*.py"; DestDir: "{app}\src\memory"; Flags: ignoreversion
Source: "src\tools\*.py"; DestDir: "{app}\src\tools"; Flags: ignoreversion
Source: "src\utils\*.py"; DestDir: "{app}\src\utils"; Flags: ignoreversion
Source: "skills\*"; DestDir: "{app}\skills"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "version.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Humanaize 2.0 Agent (ARM64)"; Filename: "{app}\Humanaize2-arm64.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"
Name: "{group}\Uninstall Humanaize 2.0 Agent"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Humanaize 2.0 Agent (ARM64)"; Filename: "{app}\Humanaize2-arm64.exe"; Parameters: "boot -m gui"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Humanaize2-arm64.exe"; Description: "{cm:LaunchProgram,Humanaize 2.0 Agent}"; Flags: nowait postinstall skipifsilent