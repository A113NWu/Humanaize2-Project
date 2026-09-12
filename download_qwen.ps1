# Qwen2.5-3B-Instruct Q4_K_M downloader (resilient, resumable)
$ErrorActionPreference = 'Stop'
$dir = 'D:\Humanaize 2.0 Agent\Humanaize2-Project\models'
$url = 'https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf'
$dst = Join-Path $dir 'Qwen2.5-3B-Instruct-Q4_K_M.gguf'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Write-Host "Downloading to: $dst"
$sw = [Diagnostics.Stopwatch]::StartNew()
# curl.exe supports retry + resume; retry up to 5 times on transient failures
for ($i = 1; $i -le 5; $i++) {
    & curl.exe -L --fail --retry 3 --retry-delay 5 -C - --connect-timeout 30 -o "$dst.tmp" $url
    if ($LASTEXITCODE -eq 0) { Move-Item "$dst.tmp" $dst -Force; break }
    Write-Host "curl exit $LASTEXITCODE, retry $i in 10s..."
    Start-Sleep 10
}
$sw.Stop()
if (Test-Path $dst) {
    $gb = [math]::Round((Get-Item $dst).Length/1GB, 2)
    Write-Host "DOWNLOAD_OK size=$gb GB elapsed=$([math]::Round($sw.Elapsed.TotalMinutes,1))min"
} else {
    Write-Host 'DOWNLOAD_FAILED'
    exit 1
}
