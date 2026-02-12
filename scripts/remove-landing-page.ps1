# 移除全屏登录页面脚本

$indexPath = "public\index.html"
$content = Get-Content $indexPath -Raw -Encoding UTF8

# 移除 HTML 部分（第 22-40 行）
$content = $content -replace '(?s)    <!-- 现代登录页面.*?</div>\s*\r?\n\s*\r?\n(?=\s*<div id="app">)', ''

# 移除 JavaScript 部分（登录页面交互代码）
$content = $content -replace '(?s)            // ========== 登录页面交互 ==========.*?// ========== 卡牌数据加载 ==========\r?\n', '            // ========== 卡牌数据加载 ==========' + "`r`n"

# 保存文件
$content | Out-File $indexPath -Encoding UTF8 -NoNewline

Write-Host "已移除全屏登录页面代码"
