# 安装可选的上游工具。城市内容台本身不依赖它们也能打开。
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Output "安装 f2（Apache-2.0，https://github.com/Johnserf-Seed/f2）"
python -m pip install --upgrade f2

New-Item -ItemType Directory -Force -Path "third_party" | Out-Null
$upload = Join-Path "third_party" "social-auto-upload"
if (-not (Test-Path $upload)) {
  Write-Output "克隆 social-auto-upload（MIT，https://github.com/dreammis/social-auto-upload）"
  git clone --depth 1 https://github.com/dreammis/social-auto-upload.git $upload
}
Write-Output "上传工具请按它自己的 README 安装依赖并登录创作者中心。装好后命令行要能运行 sau。"
Write-Output "本脚本不会克隆 MediaCrawler。那个仓库的许可证写明不得用于商业用途。"
