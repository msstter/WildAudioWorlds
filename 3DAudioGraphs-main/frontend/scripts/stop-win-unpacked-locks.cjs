const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

if (process.platform !== 'win32') {
    process.exit(0);
}

const frontendRoot = path.resolve(__dirname, '..');
const unpackedExePath = path.join(frontendRoot, 'dist', 'win-unpacked', '3D Audio Maker.exe');

if (!fs.existsSync(unpackedExePath)) {
    process.exit(0);
}

const normalizedExePath = unpackedExePath.replace(/'/g, "''");
const psCommand = [
    `$target = '${normalizedExePath}'`,
    `$processes = Get-CimInstance Win32_Process -Filter "Name = '3D Audio Maker.exe'" | Where-Object { $_.ExecutablePath -and ([System.IO.Path]::GetFullPath($_.ExecutablePath) -eq $target) }`,
    'if (-not $processes) { exit 0 }',
    '$processes | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }',
].join('; ');

const result = spawnSync(
    'powershell.exe',
    ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', psCommand],
    { stdio: 'inherit' },
);

if (result.error) {
    throw result.error;
}

process.exit(result.status ?? 0);