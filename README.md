# QL-WPS-QQBot · WPS 自动签到 + QQ 机器人通知

> 基于 [Hayfan-wu/QL-WPS](https://github.com/Hayfan-wu/QL-WPS) 整合，增加 QQ 机器人（NapCatQQ）通知能力，并兼容 QQ 机器人保存的多账号 Cookie 格式。

## 功能特性

- **每日签到** — WPS 会员中心自动签到
- **自适应任务引擎** — click/share/scan/browse 等任务自动完成
- **自动抽奖** — 消耗可用抽奖次数
- **多账号支持** — 支持 `WPS_COOKIE` 多账号，也支持 `WPS_COOKIE_账号备注` 格式
- **WXPusher 推送** — 微信推送汇总报告
- **QQ 机器人通知** — 通过 NapCatQQ 发送签到结果到 QQ 群/私聊
- **青龙适配** — 通过环境变量注入凭据

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 Cookie

#### 方式一：单环境变量多账号（原 QL-WPS 方式）

```bash
export WPS_COOKIE="账号1的Cookie
账号2的Cookie"
```

多账号用换行或 `&` 分隔。

#### 方式二：配合 QQ 机器人多账号管理（推荐）

通过 QQ 机器人提交 Cookie 后，会自动保存为青龙环境变量：

```text
WPS_COOKIE_账号1=xxxxxx
WPS_COOKIE_账号2=xxxxxx
```

脚本会自动读取所有 `WPS_COOKIE_` 前缀的环境变量。

### 3. 配置 QQ 机器人通知

```bash
export QQ_BOT_API="http://127.0.0.1:3000"
export QQ_BOT_TOKEN="your_napcat_token"
export QQ_GROUP_ID="123456789"   # 发送到群
# 或
export QQ_USER_ID="123456789"    # 发送到私聊
```

### 4. 运行

```bash
python3 wps_auto.py
```

## 青龙面板部署

1. **添加脚本**：将 `wps_auto.py` 上传到青龙 `scripts` 目录
2. **安装依赖**：青龙依赖管理 → Python → 添加 `requests`、`pycryptodome`
3. **配置环境变量**：
   - `WPS_COOKIE` 或 `WPS_COOKIE_账号备注`：WPS Cookie
   - `QQ_BOT_API`：NapCat HTTP API 地址
   - `QQ_BOT_TOKEN`：NapCat Access Token（可选）
   - `QQ_GROUP_ID`：目标 QQ 群号（可选）
   - `QQ_USER_ID`：目标 QQ 号（可选）
4. **创建定时任务**：
   - 命令：`task wps_auto.py`
   - 定时规则：`30 8 * * *`（每天 8:30 执行）

## 与 QQ 机器人配合使用

本脚本可与 [WPS QQ 机器人方案](../wps-qq-bot-guide.md) 联动：

1. 在 QQ 中发送：`WPS登录 账号1 xxxxxxx`
2. 机器人将 Cookie 保存为青龙环境变量 `WPS_COOKIE_账号1`
3. 青龙定时执行 `wps_auto.py`，自动读取所有 `WPS_COOKIE_` 前缀的账号
4. 执行结果通过 QQ 机器人推送到群/私聊

## 配置项

| 配置 | 环境变量 | 说明 |
|---|---|---|
| 账号 Cookie | `WPS_COOKIE` | 多账号用换行或 `&` 分隔 |
| QQ 机器人 API | `QQ_BOT_API` | NapCat OneBot HTTP 地址 |
| QQ 机器人 Token | `QQ_BOT_TOKEN` | NapCat Access Token |
| QQ 群号 | `QQ_GROUP_ID` | 推送目标群 |
| QQ 号 | `QQ_USER_ID` | 推送目标私聊 |
| WxPusher Token | `WXPUSHER_APP_TOKEN` | 微信推送 Token |
| WxPusher UID | `WXPUSHER_UID` | 微信推送 UID |

## 运行示例

```text
[15:28:39] [+] 账号登录有效，用户：昊龙（uid=255460626）
[15:28:39] [*] 签到状态：今日已签=True 本月连续=1天 累计=1天
[15:28:39] [+] 今日已签到，跳过
[15:28:40] >>> 任务清单
...
[15:28:51] >>> 开始自动抽奖
[15:29:15] [+] 抽奖完毕，共中奖 10 次
[15:29:16] [+] QQ 消息发送成功
```

## 文件说明

```text
QL-WPS-QQBot/
├── wps_auto.py       # 主脚本（已整合 QQ 通知）
├── requirements.txt  # Python 依赖
└── README.md         # 说明文档
```

## 注意事项

- 本脚本仅供学习交流使用
- Cookie 存在有效期，失效后需重新获取
- 请勿将含真实 Cookie 的脚本提交到公开仓库
- 建议每日执行一次，频繁请求可能触发风控
