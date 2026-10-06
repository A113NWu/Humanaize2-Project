# 内网穿透快速启动
# 使用前：把 ngrok authtoken 写入 ~/.ngrok2/ngrok.yml 的 authtoken 行（去掉注释）

# 后台启动两条隧道
Start-Process -NoNewWindow -FilePath "ngrok" -ArgumentList "start --all --config ~/.ngrok2/ngrok.yml" -RedirectStandardOutput "$env:TEMP\ngrok.log" -RedirectStandardError "$env:TEMP\ngrok_err.log"
Start-Sleep 3

# 显示隧道地址
$log = Get-Content "$env:TEMP\ngrok.log" -ErrorAction SilentlyContinue
$log | Select-String "url=" | ForEach-Object { $_.Line.Trim() }
"---"
"隧道状态查询: http://127.0.0.1:4040/api/tunnels"
