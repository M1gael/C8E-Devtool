# Baseline capture — run BEFORE each config phase (A, then again before B, then C).
# Usage: .\capture-baseline.ps1 -Config A-vanilla
# Writes baselines\<Config>\: baseline.json + raw dumps. Re-running overwrites.
param([string]$Config = "A-vanilla")

$ErrorActionPreference = "Continue"
$out = Join-Path $PSScriptRoot $Config
New-Item -ItemType Directory -Force $out | Out-Null

$agHome  = "$env:LOCALAPPDATA\Programs\Antigravity IDE"
$agCli   = "$agHome\bin\antigravity-ide.cmd"
$extDir  = "$env:USERPROFILE\.antigravity-ide\extensions"
$userDir = "$env:APPDATA\Antigravity IDE\User"
$gemini  = "$env:USERPROFILE\.gemini"
$devkit  = "$env:USERPROFILE\Documents\antigravity-devkit"

function Save([string]$name, $content) {
    $content | Out-File -FilePath (Join-Path $out $name) -Encoding utf8
}

function HashTree([string]$root, [long]$maxHashBytes = 5MB) {
    # every file: relative path, size, mtime; SHA256 for files under the cap
    if (-not (Test-Path $root)) { return @() }
    Get-ChildItem $root -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $h = ""
        if ($_.Length -le $maxHashBytes) {
            try { $h = (Get-FileHash $_.FullName -Algorithm SHA256 -ErrorAction Stop).Hash } catch {}
        }
        [PSCustomObject]@{
            path  = $_.FullName.Substring($root.Length + 1)
            bytes = $_.Length
            mtime = $_.LastWriteTimeUtc.ToString("o")
            sha256 = $h
        }
    }
}

$b = [ordered]@{}

# ---- meta
$b.meta = [ordered]@{
    config    = $Config
    captured  = (Get-Date).ToUniversalTime().ToString("o")
    hostname  = $env:COMPUTERNAME
    username  = $env:USERNAME
}

# ---- OS
$os = Get-CimInstance Win32_OperatingSystem
$b.os = [ordered]@{
    caption = $os.Caption
    version = $os.Version
    build   = $os.BuildNumber
}

# ---- Antigravity install + version
$agVersion = @()
if (Test-Path $agCli) { $agVersion = & $agCli --version 2>&1 | ForEach-Object { "$_" } }
$b.antigravity = [ordered]@{
    install_dir     = $agHome
    installed       = (Test-Path $agHome)
    cli             = $agCli
    version_output  = $agVersion
    cli_on_path     = [bool](Get-Command antigravity -ErrorAction SilentlyContinue)
}

# ---- Extensions: CLI view + directory view
$extCli = @()
if (Test-Path $agCli) { $extCli = & $agCli --list-extensions --show-versions 2>&1 | ForEach-Object { "$_" } }
Save "extensions-cli.txt" ($extCli -join "`r`n")
$extFolders = @()
if (Test-Path $extDir) {
    $extFolders = Get-ChildItem $extDir -Directory | Select-Object -ExpandProperty Name
    if (Test-Path "$extDir\extensions.json") {
        Copy-Item "$extDir\extensions.json" (Join-Path $out "extensions-registry.json") -Force
    }
}
Save "extensions-dir.txt" ($extFolders -join "`r`n")
$b.extensions = [ordered]@{
    cli_list    = ($extCli | Where-Object { $_ -notmatch "createInstance" })
    dir         = $extDir
    dir_folders = $extFolders
    count_dir   = $extFolders.Count
}

# ---- User settings (absence of settings.json = OOB defaults, significant)
$settings = "$userDir\settings.json"
$b.user_settings = [ordered]@{
    user_dir             = $userDir
    settings_json_exists = (Test-Path $settings)
    user_dir_entries     = @(if (Test-Path $userDir) { (Get-ChildItem $userDir -Force | Select-Object -ExpandProperty Name) })
}
if (Test-Path $settings) { Copy-Item $settings (Join-Path $out "settings.json") -Force }
$argv = "$env:USERPROFILE\.antigravity-ide\argv.json"
if (Test-Path $argv) { Copy-Item $argv (Join-Path $out "argv.json") -Force }

# ---- Gemini / agent state (full hash tree — MCP config would live here)
$geminiTree = HashTree $gemini
$geminiTree | ConvertTo-Json -Depth 3 | Out-File (Join-Path $out "gemini-tree.json") -Encoding utf8
$b.gemini = [ordered]@{
    dir        = $gemini
    file_count = @($geminiTree).Count
    agents_md  = (Test-Path "$gemini\AGENTS.md")
}

# ---- MCP config discovery (any mcp*.json in agent/user dirs)
$mcpHits = @()
foreach ($root in @($gemini, $userDir, "$env:APPDATA\Antigravity")) {
    if (Test-Path $root) {
        $mcpHits += Get-ChildItem $root -Recurse -Force -ErrorAction SilentlyContinue -Include "*mcp*.json", "mcp_config*" |
            Select-Object -ExpandProperty FullName
    }
}
$b.mcp_config_files = $mcpHits

# ---- Toolchain
function Ver([string]$cmd, [string]$argv1 = "--version") {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($null -eq $c) { return "not on PATH" }
    try { return ((& $cmd $argv1 2>&1 | Select-Object -First 1) -join "") } catch { return "error" }
}
$b.toolchain = [ordered]@{
    python = Ver "python"
    pip    = Ver "pip"
    uv     = Ver "uv"
    tina4  = Ver "tina4"
    git    = Ver "git"
    node   = Ver "node"
    npm    = Ver "npm"
}
$pipList = @()
if (Get-Command pip -ErrorAction SilentlyContinue) { $pipList = pip list 2>$null | ForEach-Object { "$_" } }
Save "pip-list.txt" ($pipList -join "`r`n")

# ---- PATH + relevant env
Save "path.txt" (($env:Path -split ";") -join "`r`n")
$b.env_tina4 = @(Get-ChildItem env: | Where-Object { $_.Name -like "TINA4*" -or $_.Name -eq "PORT" } |
    ForEach-Object { "$($_.Name)=$($_.Value)" })

# ---- Devkit pin (exact devkit content that config B will deploy)
$devkitTree = HashTree $devkit
$devkitTree | ConvertTo-Json -Depth 3 | Out-File (Join-Path $out "devkit-hashes.json") -Encoding utf8
$b.devkit = [ordered]@{
    dir        = $devkit
    file_count = @($devkitTree).Count
}

# ---- Eval ports free?
$busy = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -ge 7000 -and $_.LocalPort -le 7040 } |
    Select-Object -ExpandProperty LocalPort -Unique)
$b.eval_ports_in_use = $busy

$b | ConvertTo-Json -Depth 6 | Out-File (Join-Path $out "baseline.json") -Encoding utf8
Write-Output "Baseline '$Config' captured to $out"
Write-Output ("extensions: {0}  settings.json: {1}  AGENTS.md: {2}  ports busy: {3}" -f `
    $b.extensions.count_dir, $b.user_settings.settings_json_exists, $b.gemini.agents_md, ($busy -join ","))
