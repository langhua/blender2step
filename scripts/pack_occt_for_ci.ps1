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
Write-Host "打包完成: $output ($size MB)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步操作：" -ForegroundColor Yellow
Write-Host "1. 前往 https://github.com/$env:GITHUB_REPOSITORY/releases/new" -ForegroundColor White
Write-Host "2. 在 'Choose a tag' 输入: occt-v1 (新建)" -ForegroundColor White
Write-Host "3. Release title 填: OCCT Pre-built" -ForegroundColor White
Write-Host "4. 上传 $output 作为 Release asset" -ForegroundColor White
Write-Host "5. 点击 'Publish release'" -ForegroundColor White
Write-Host ""
Write-Host "之后每次 CI 运行都会自动下载这个预编译包，无需再编译 OCCT。" -ForegroundColor Green
