#ifndef RepoRoot
  #define RepoRoot AddBackslash(SourcePath) + ".."
#endif

#ifndef OutputDir
  #define OutputDir AddBackslash(RepoRoot) + "build\\windows-installer"
#endif

#ifndef AppVersion
  #define AppVersion "2026.05.16"
#endif

#define AppName "Bioacoustics Rhythm Pipeline"
#define AppExeName "BioacousticsRhythmPipeline.exe"

[Setup]
AppId={{DAB4DD89-5505-43EA-8C90-7B6CB613D66A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
AppPublisherURL=https://github.com/
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile={#RepoRoot}\GUI\DesktopIcon.ico
UninstallDisplayIcon={app}\GUI\DesktopIcon.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputDir={#OutputDir}
OutputBaseFilename=BioacousticsRhythmPipelineSetup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\environment.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\pipeline_config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "{#RepoRoot}\GUI\*"; DestDir: "{app}\GUI"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".DS_Store,._*,__pycache__\*,*.pyc,test_*.py,Bioacoustics Rhythm Pipeline.app\*"
Source: "{#RepoRoot}\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "{#RepoRoot}\analysis\*"; DestDir: "{app}\analysis"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "{#RepoRoot}\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".DS_Store,._*"

[Dirs]
Name: "{app}\audioFiles"
Name: "{app}\AnalysisReports"
Name: "{app}\Association_Rules"
Name: "{app}\data"
Name: "{app}\GLMM"
Name: "{app}\Histogram_Plots"
Name: "{app}\KS_Test"
Name: "{app}\Lag1_Autocorrelation"
Name: "{app}\Mantel_Test"
Name: "{app}\nPVI_Group_Plots"
Name: "{app}\pDFA"
Name: "{app}\PGLS"
Name: "{app}\Raincloud_Metrics"
Name: "{app}\Raster_Plots"
Name: "{app}\Rhythm_Ratios"
Name: "{app}\Tempo_Ratio_Heatmap"
Name: "{app}\Wilcoxon_Isochrony"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\GUI\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\GUI\DesktopIcon.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\GUI\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\GUI\DesktopIcon.ico"

[Run]
Filename: "{app}\GUI\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function HasRhythmEnv: Boolean;
var
  UserProfile: string;
  LocalAppData: string;
begin
  UserProfile := GetEnv('USERPROFILE');
  LocalAppData := GetEnv('LOCALAPPDATA');
  Result :=
    FileExists(UserProfile + '\\anaconda3\\envs\\rhythm_env\\python.exe') or
    FileExists(UserProfile + '\\miniconda3\\envs\\rhythm_env\\python.exe') or
    FileExists(LocalAppData + '\\anaconda3\\envs\\rhythm_env\\python.exe') or
    FileExists(LocalAppData + '\\miniconda3\\envs\\rhythm_env\\python.exe') or
    FileExists('C:\\ProgramData\\anaconda3\\envs\\rhythm_env\\python.exe');
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not HasRhythmEnv then
    SuppressibleMsgBox(
      'This installer adds the Bioacoustics Rhythm Pipeline app files, Start Menu entry, and uninstaller.' + #13#10#13#10 +
      'It does not create the Conda environment automatically.' + #13#10#13#10 +
      'If you have not already created rhythm_env from environment.yml, do that first from Anaconda Prompt.',
      mbInformation,
      MB_OK,
      IDOK
    );
end;