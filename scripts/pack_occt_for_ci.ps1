# pack_occt_for_ci.ps1
# 将本地预编译的 OCCT 打包为 zip，准备上传到 GitHub Release
# 用法：在仓库根目录运行 .\scripts\pack_occt_for_ci.ps1
# 然后手动创建 GitHub Release，上传生成的 zip 文件

param(
    [string]$OutputDir = "$PSScriptRoot\.."
)

$source = "$PSScriptRoot\..\vcpkg_installed\x64-windows-release"
$output = "$OutputDir\occt-x64-windows-release.zip"

if (-not (Test-Path $source)) {
    Write-Host "ERROR: 找不到 $source" -ForegroundColor Red
    Write-Host "请确认 vcpkg_installed\x64-windows-release 目录存在" -ForegroundColor Red
    exit 1
}

Write-Host "正在打包: $source" -ForegroundColor Green
Write-Host "输出文件: $output" -ForegroundColor Green

# 仅打包必要的子目录（排除 debug 和 tools 减小体积）
Compress-Archive -Path "$source\include", "$source\lib", "$source\share", "$source\bin" -DestinationPath $output -Force

$size = [math]::Round((Get-Item $output).Length / 1MB, 1)
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Done: $output ($size MB)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host " 1. Go to https://github.com/langhua/blender2step/releases/new"
Write-Host " 2. Tag: occt-v1 (create new)"
Write-Host " 3. Title: OCCT 7.8.1 Pre-built"
Write-Host " 4. Upload the zip file as Release asset"
Write-Host " 5. Click Publish release"
Write-Host ""
Write-Host "After this, CI will auto-download the package every run." -ForegroundColor Green
