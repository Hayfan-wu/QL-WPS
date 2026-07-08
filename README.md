# QL-WPS-QQBot · WPS 自动签到 + QQ 交互式机器人

> 基于 [Hayfan-wu/QL-WPS](https://github.com/Hayfan-wu/QL-WPS) 整合，新增 QQ 机器人交互式 Cookie 提交、青龙环境变量管理、签到结果 QQ 通知。

## 核心流程

```text
用户 @机器人 账号:wps 登录
        ↓
机器人回复：请输入账号备注
        ↓
用户发送：账号1
        ↓
机器人回复：请输入账号 [账号1] 的 Cookie
        ↓
用户发送 Cookie
        ↓
机器人自动保存到青龙环境变量
```

## 文件结构

```text
QL-WPS-QQBot/
├── wps_auto.py       # WPS 自动签到脚本（支持 QQ 通知）
├── wps_bot.py        # QQ 机器人服务端（新增）
├── requirements.txt  # Python 依赖
├── .env.example      # 环境变量示例
├── wps-bot.service   # systemd 服务示例
└── README.md         # 本文档
```

## 功能列表

| 命令 | 说明 |
|---|---|
| `@机器人 账号:wps 登录` | 交互式登录，按提示输入账号备注和 Cookie |
| `@机器人 WPS登录 账号1 cookie` | 一键登录，直接保存到青龙环境变量 |
| `@机器人 WPS查询 账号1` | 查询账号是否已保存及环境变量状态 |
| `@机器人 WPS列表` | 列出所有已保存的 WPS 账号 |
| `@机器人 WPS管理 登出 账号1` | 删除指定账号的 Cookie |
| `@机器人 帮助` | 显示命令列表 |

## 部署步骤

### 第一步：安装依赖

```bash
cd /opt
mkdir -p wps-bot
cd wps-bot
pip install requests pycryptodome websockets --break-system-packages
```

### 第二步：下载脚本

```bash
curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/wps_bot.py
curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/wps_auto.py
curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/requirements.txt
```

### 第三步：配置环境变量

创建 `.env` 文件：

```bash
cat > .env <<EOF
# 机器人自己的 QQ 号（必须配置，用于识别群 @）
QQ_BOT_QQ=123456789

# NapCat HTTP API（用于机器人回复 QQ 消息）
NAPCAT_API=http://127.0.0.1:3000
NAPCAT_TOKEN=your_napcat_token

# 青龙面板 Open API
QL_URL=http://127.0.0.1:5700
QL_CLIENT_ID=your_client_id
QL_CLIENT_SECRET=your_client_secret

# 允许的 QQ 管理员，多个用逗号分隔，留空表示不限制
ADMIN_QQ=你的QQ号

# 机器人 WebSocket 监听配置
WS_HOST=0.0.0.0
WS_PORT=8080
WS_PATH=/onebot/v11/ws/
EOF
```

### 第四步：获取青龙 Client ID / Client Secret

1. 登录青龙面板
2. 系统设置 → 应用设置 → 新建应用
3. 名称：`wps-bot`
4. 权限勾选：`环境变量`
5. 复制生成的 `Client ID` 和 `Client Secret`

### 第五步：配置 NapCat 反向 WebSocket

1. 打开 NapCat WebUI：`http://服务器IP:6099/webui`
2. 进入「网络配置」→「OneBot 11」
3. 新建 **Websocket客户端**：

```text
名称：wps-bot
启用：是
Host：127.0.0.1
端口：8080
路径：/onebot/v11/ws/
Access Token：（可选，与 .env 中 WS_TOKEN 保持一致）
消息上报格式：string
```

4. 保存并重启 NapCat 容器：

```bash
docker restart napcat
```

### 第六步：启动机器人

```bash
cd /opt/wps-bot
export $(cat .env | grep -v '^#' | xargs)
nohup python3 wps_bot.py > bot.log 2>&1 &
```

查看日志：

```bash
tail -f bot.log
```

### 第七步：群里测试

发送：

```text
@机器人 账号:wps 登录
```

机器人应回复：

```text
请输入账号备注，例如：账号1
```

## 青龙定时任务配置

1. 上传 `wps_auto.py` 到青龙 `scripts` 目录
2. 安装依赖：`requests`、`pycryptodome`
3. 配置环境变量：
   - `QQ_BOT_API`、`QQ_BOT_TOKEN`、`QQ_GROUP_ID` 或 `QQ_USER_ID`
   - 机器人保存的 `WPS_COOKIE_账号备注` 会自动被读取
4. 创建定时任务：
   - 命令：`task wps_auto.py`
   - 定时：`30 8 * * *`（每天 8:30 执行）

## 常见问题

### 群里 @ 机器人无反应

1. 检查 `QQ_BOT_QQ` 是否配置正确
2. 检查 NapCat 反向 WS 是否连接成功（看 `bot.log`）
3. 检查机器人是否在目标群里
4. 检查 `ADMIN_QQ` 是否限制了发送者
5. 检查 8080 端口是否放行

### 机器人连接后立即断开

可能是 NapCat 鉴权失败，检查 `.env` 中的 `WS_TOKEN` 是否与 NapCat 中配置的 Access Token 一致。

### Cookie 保存失败

1. 检查青龙应用权限是否包含「环境变量」
2. 检查 `QL_CLIENT_ID` 和 `QL_CLIENT_SECRET` 是否正确
3. 查看 `bot.log` 中的具体错误信息

## 安全提醒

- 使用 QQ 小号作为机器人，不要用主号
- Cookie 是敏感信息，不要截图发送到公开群
- 建议设置 `ADMIN_QQ` 限制只有你能操作
- 青龙应用只授予「环境变量」权限，不要给过多权限

## 更新日志

- 2025-07-08：新增 QQ 机器人交互式登录流程，支持群 @ 消息处理
- 2025-07-08：WPS 签到脚本增加 NapCatQQ 通知
- 2025-07-08：兼容 `WPS_COOKIE_账号备注` 多账号格式
