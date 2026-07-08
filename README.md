# QL-WPS · WPS 会员中心自动签到 & 任务 & 抽奖 & 机器人管理

青龙面板（QingLong）/ 本地均可使用的 WPS 会员中心自动化脚本，支持签到、任务、抽奖、消息推送，以及 **Telegram 机器人** 和 **QQ 机器人** 两种交互式管理方式。

通过逆向分析 WPS 活动页面的前端加密逻辑与任务接口，实现**纯接口**完成签到、多种类型任务和自动抽奖，无需浏览器自动化，稳定高效。

## 功能特性

- **每日签到** — 自动完成 WPS 会员中心每日签到，领取积分与勋章
- **自适应任务引擎** — 按任务类型（task_event）+ 状态（task_status）自动选择完成策略，不硬编码任务ID，任务变更后仍能自适应处理
- **多类型任务支持** — click/share/scan 直接 finish 完成、browse 浏览任务完整流程、exchange_traffic 换量任务自动访问
- **待领奖自动领取** — 检测到待领奖状态（toReceive）自动领取奖励
- **自动抽奖** — 自动消耗所有可用抽奖次数，执行九宫格抽奖，汇总中奖结果
- **WXPusher 推送** — 执行完毕后推送汇总报告到微信（签到状态、任务统计、中奖明细）
- **多账号** — 支持环境变量配置多个账号，循环执行
- **青龙适配** — 通过环境变量注入凭据，适配青龙面板定时任务
- **Telegram 机器人** — 通过 TG Bot 提交 Cookie、查询状态、管理青龙变量、立即执行任务，45 秒会话超时
- **QQ 机器人（NapCatQQ）** — 通过 QQ 群 @机器人 完成登录/查询/管理，插件化架构便于扩展

## 已验证能力

| 功能 | 策略 | 状态 | 说明 |
| --- | --- | --- | --- |
| 签到 | RSA+AES加密 | ✅ 可用 | 已实测签到成功 |
| click（点击） | task_center.finish + reward | ✅ 可用 | 14个click任务实测全部完成 |
| share（分享） | task_center.finish + reward | ✅ 可用 | 实测完成 |
| scan（扫描） | task_center.finish + reward | ✅ 可用 | 同click机制 |
| browse（浏览） | start → task_info → 等待 → finish → reward | ✅ 可用 | 全链路实测通过 |
| exchange_traffic（换量） | start → 访问jump_url → finish → reward | ⚠️ 部分 | 需目标App内操作，纯接口可能失败 |
| toReceive（待领奖） | 直接 reward | ✅ 可用 | 自动检测并领取 |
| **自动抽奖** | lottery_v2.exec | ✅ 可用 | 10次实测全部中奖（1积分/3积分） |
| **WXPusher 推送** | /api/send/message | ✅ 可用 | markdown格式汇总报告推送到微信 |
| **Telegram Bot** | python-telegram-bot | ✅ 可用 | 支持登录/查询/管理/执行 |
| **QQ Bot** | NapCatQQ + 反向 WS | ✅ 可用 | 插件化，支持群 @ 交互 |
| trade/auth/invite/subscribe | — | ❌ 需手动 | 需支付/认证/微信环境等，无法纯接口完成 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 Cookie

脚本通过环境变量 `WPS_COOKIE` 读取账号 Cookie（推荐），也可直接编辑脚本中的 `DEFAULT_COOKIE`。

```bash
# 单账号
export WPS_COOKIE="你的WPS账号Cookie"

# 多账号（用换行或 & 分隔）
export WPS_COOKIE="账号1的Cookie
账号2的Cookie"
```

### 3. 运行签到脚本

```bash
python3 wps_auto.py
```

## 获取 Cookie

1. 浏览器访问 [WPS 个人中心](https://account.wps.cn) 并登录
2. 按 `F12` 打开开发者工具，切换到 **Network** 标签
3. 刷新页面，点击任意一个请求
4. 在 **Request Headers** 中找到 `Cookie` 字段，复制完整值

> Cookie 中关键字段为 `wps_sid`、`kso_sid`、`csrf`、`uid`，缺一不可。

## WXPusher 推送配置（可选）

启用后，脚本执行完毕会自动推送汇总报告到微信，包含签到状态、任务统计、中奖明细。

1. 访问 [WxPusher 后台](https://wxpusher.zjiecode.com/admin/)，微信扫码登录
2. 创建应用，获取 `appToken`
3. 关注公众号「wxpusher」，在「我的 → 我的UID」获取 `uid`
4. 配置环境变量：
   ```bash
   export WXPUSHER_APP_TOKEN="AT_xxxxxxxx"
   export WXPUSHER_UID="UID_xxxxxxxx"
   ```
5. 不配置则不推送，仅控制台输出

## 青龙面板部署

1. **添加脚本**：在青龙面板「脚本管理」中拉取本仓库，或手动上传 `wps_auto.py`
2. **安装依赖**：在「依赖管理 → Python」中添加 `requests`、`pycryptodome`
3. **配置环境变量**：在「环境变量」中新增
   - `WPS_COOKIE`：WPS 账号 Cookie（多账号换行或用 `&` 分隔）
   - `WXPUSHER_APP_TOKEN`：WxPusher 应用 Token（可选，用于推送通知）
   - `WXPUSHER_UID`：WxPusher 用户 UID（可选，用于推送通知）
4. **创建定时任务**：
   - 命令：`task wps_auto.py`（青龙）或 `python3 wps_auto.py`
   - 定时规则：`30 8 * * *`（每天 8:30 执行）

## Telegram 机器人（推荐，按流程图实现）

通过 Telegram Bot 与青龙联动，实现“粘贴 Cookie → 自动验证 → 自动写入青龙环境变量”的完整流程。

### 机器人命令

| 命令 | 说明 |
| --- | --- |
| `/start` | 欢迎与帮助 |
| `/help` | 查看使用帮助 |
| `/wps_login` | 提交/更新 WPS Cookie 到青龙环境变量 |
| `/wps_query` | 查询 WPS 账号状态、签到、任务、抽奖次数 |
| `/wps_manage` | 查看青龙环境变量中的 WPS_COOKIE |
| `/wps_exec` | 立即执行一次 `wps_auto.py` 签到任务 |
| `/cancel` | 取消当前会话 |

### 机器人环境变量

```bash
export BOT_TOKEN="你的 Telegram Bot Token"
export ALLOWED_USER_IDS="123456789,987654321"  # 可选，限制可使用的用户 ID
export QL_URL="http://127.0.0.1:5700"          # 青龙面板地址
export QL_CLIENT_ID="你的青龙应用 client_id"
export QL_CLIENT_SECRET="你的青龙应用 client_secret"
```

### 启动机器人

```bash
python3 tg_bot.py
```

### 使用流程

```
用户：/wps_login
机器人：🍪 请输入你的 WPS Cookie（支持多账号，用换行或 & 分隔）：
        提示：45 秒内未输入将自动取消。

用户：<粘贴 Cookie>
机器人：🔍 正在验证 WPS Cookie 并获取账号信息...
机器人：✅ WPS 验证成功：xxx（uid=12345678）
        🚀 正在提交到青龙环境变量 WPS_COOKIE...
机器人：🎉 登录成功并已提交到青龙！
        👤 账号：xxx
        🆔 uid：12345678
        📦 环境变量：WPS_COOKIE
        ⏰ 时间：2025-07-08 10:00:00
        你可以使用 /wps_query 查询状态，/wps_exec 立即执行任务。
```

### 群聊使用

- 第一次需要 `@机器人 wps登录` 唤醒机器人
- 进入登录会话后，45 秒内直接粘贴 Cookie 即可，无需重复 `@`
- 其他命令如 `@机器人 wps查询`、`@机器人 wps执行` 也可通过 @ 触发
- 如果机器人在群里不响应没有 @ 的消息，请至 @BotFather 关闭该机器人的 **Privacy Mode**：
  `/setprivacy` → 选择你的机器人 → `Disable`

### 青龙 Client ID 如何获取

青龙 `client_id` 和 `client_secret` 需要在青龙面板中创建一个**应用**来获取：

1. 登录青龙面板
2. 进入「系统设置」→「应用设置」
3. 点击「新建应用」
4. 名称任意，例如 `ql-wps-bot`
5. **权限勾选「环境变量」**
6. 保存后复制 `client_id` 和 `client_secret`
7. 填入机器人的 `QL_CLIENT_ID` 和 `QL_CLIENT_SECRET` 环境变量

> 一个应用对应一组 `client_id`/`client_secret`，名称可以自定义，只要权限包含环境变量即可。

## QQ 机器人（NapCatQQ，插件化框架）

基于 NapCatQQ 反向 WebSocket 的通用 QQ 机器人框架。除了 WPS 管理外，还可以在 `bot/plugins/` 下新增插件文件来扩展功能。

### 目录结构

```text
.
├── main.py                 # QQ 机器人启动入口
├── bot/
│   ├── config.py           # 配置管理
│   ├── core.py             # 核心：WS 服务、插件加载、消息分发
│   ├── utils.py            # 日志、消息发送、文本清理
│   ├── ql_api.py           # 青龙 API 封装
│   ├── session.py          # 用户会话状态管理
│   └── plugins/
│       ├── base.py         # 插件基类
│       ├── wps.py          # WPS 账号管理插件
│       └── example.py      # 新增插件参考示例
```

### 启动

```bash
export $(cat .env | grep -v '^#' | xargs)
python3 main.py
```

### 交互命令

```text
@机器人 账号:wps 登录          # 交互式登录
@机器人 WPS登录 账号1 cookie  # 一键登录
@机器人 WPS查询 账号1          # 查询账号
@机器人 WPS列表                # 列出所有账号
@机器人 WPS管理 登出 账号1     # 删除账号
@机器人 帮助                   # 显示命令列表
```

详细部署步骤可参考 `.env.example` 和 `wps-bot.service`。

## 配置项

| 配置 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 账号 Cookie | `WPS_COOKIE` | 空 | 多账号用换行或 `&` 分隔 |
| WxPusher Token | `WXPUSHER_APP_TOKEN` | 空 | 推送应用 Token |
| WxPusher UID | `WXPUSHER_UID` | 空 | 推送用户 UID |
| Telegram Bot Token | `BOT_TOKEN` | 空 | Telegram Bot Token |
| Telegram 允许用户 | `ALLOWED_USER_IDS` | 空 | 可选，逗号分隔用户 ID |
| QQ 机器人 QQ 号 | `QQ_BOT_QQ` | 空 | 用于识别群 @ 消息 |
| QQ 管理员 | `ADMIN_QQ` | 空 | 可选，逗号分隔 QQ 号 |
| 青龙地址 | `QL_URL` | 空 | 青龙面板地址 |
| 青龙 Client ID | `QL_CLIENT_ID` | 空 | 青龙应用 client_id |
| 青龙 Secret | `QL_CLIENT_SECRET` | 空 | 青龙应用 client_secret |
| 是否签到 | — | `True` | 修改脚本 `DO_SIGN_IN` |
| 是否抽奖 | — | `True` | 修改脚本 `DO_LOTTERY` |
| 浏览等待冗余 | — | `3` 秒 | 修改脚本 `BROWSE_EXTRA_WAIT` |
| finish后等待 | — | `3` 秒 | 修改脚本 `FINISH_DELAY` |
| 抽奖间隔 | — | `2` 秒 | 修改脚本 `LOTTERY_INTERVAL` |
| 请求间隔 | — | `1.5` 秒 | 修改脚本 `REQUEST_INTERVAL` |

## 运行示例

```
[15:28:39] [+] 账号登录有效，用户：昊龙（uid=255460626）
[15:28:39] [*] 签到状态：今日已签=True 本月连续=1天 累计=1天
[15:28:39] [+] 今日已签到，跳过
[15:28:40] >>> 任务清单
  ID 状态   类型               标题
  5  已完成  browse           浏览福利中心10s
  6  已完成  browse           浏览积分商城10s
 17  已完成  click            体验1次拍照扫描
 33  已完成  share            分享好友
 ...
[15:28:40] [*] 待处理任务 7 个（共 24 个）
[15:28:50] >>> 任务完成汇总：成功 0 / 跳过 5 / 失败 2
[15:28:51] >>> 开始自动抽奖
[15:28:51] [*] 当前积分：42
[15:28:51] [*] 场次 2：剩余 10 次，类型=次数抽奖
[15:28:53] [+] 第 1/10 次抽奖：中奖 1积分（integral）
[15:28:55] [+] 第 2/10 次抽奖：中奖 3积分（integral）
...
[15:29:15] [+] 抽奖完毕，共中奖 10 次：1积分、3积分、1积分...
```

## 实现原理

**签到加密流程**（`personal-bus.wps.cn/sign_in/v1/sign_in`）：

1. `GET /encrypt/key` 获取 RSA 公钥（PKCS#1 格式）
2. 生成 32 字符 AES 密钥（22 位随机字符 + 10 位时间戳）
3. RSA-PKCS1v1.5 加密 AES 密钥 → 作为请求头 `token`
4. AES-CBC（key=32字节, iv=前16字节, Pkcs7）加密 `{user_id, platform}` → 作为请求体 `extra`

**自适应任务分发**（`activity-rubik/activity/component_action`）：

脚本通过 `page_info` 接口获取任务列表，按 `task_event`（类型）和 `task_status`（状态）自动选择策略：

| 状态 | 类型 | 策略 |
| --- | --- | --- |
| done(2) | 任意 | 跳过 |
| toReceive(1) | 任意 | 直接 `task_center.reward` 领奖 |
| undone(0) | click/share/scan | `task_center.finish` → 等待3s → `reward` |
| undone(0) | browse | `start` → `task_info` → 等待 → `task_finish` → `reward` |
| undone(0) | exchange_traffic | `start` → 访问 `jump_url+token` → `finish` → `reward` |
| undone(0) | trade/auth/invite等 | 跳过并提示 |

> 未知类型会自动尝试通用 `finish` 策略，确保新任务类型也能处理。

**自动抽奖流程**（`activity-rubik/activity/component_action`）：

1. `GET page_info` 获取抽奖组件 `lottery_v2` 数据（场次、剩余次数、积分）
2. 遍历 `IN_PROGRESS` 且 `times > 0` 的场次
3. `POST component_action` body=`{component_action: "lottery_v2.exec", lottery_v2: {session_id}}` 执行抽奖
4. 解析返回的 `reward_name`、`reward_type`，汇总中奖结果
5. 遇到 error_code 10005（次数用完）或 10007（达到最大中奖数）自动停止

**WXPusher 推送**（`wxpusher.zjiecode.com/api/send/message`）：

脚本执行完毕后，通过 WXPusher HTTP API 推送 markdown 格式汇总报告，包含签到状态、任务统计、中奖明细。

## 文件说明

```
QL-WPS/
├── wps_auto.py       # 主脚本（签到/任务/抽奖/推送）
├── tg_bot.py         # Telegram 机器人
├── wps_query.py      # WPS 信息查询模块（只读，供 tg_bot 使用）
├── qinglong_api.py   # 青龙面板 Open API 封装（供 tg_bot 使用）
├── main.py           # QQ 机器人启动入口
├── bot/              # QQ 机器人插件化框架
│   ├── config.py
│   ├── core.py
│   ├── utils.py
│   ├── ql_api.py
│   ├── session.py
│   └── plugins/
│       ├── base.py
│       ├── wps.py
│       └── example.py
├── .env.example      # 环境变量模板（包含 Telegram + QQ + 青龙）
├── wps-bot.service   # QQ 机器人 systemd 服务模板
├── requirements.txt  # Python 依赖
└── README.md         # 说明文档
```

## 注意事项

- 本脚本仅供学习交流使用，请勿用于商业用途
- Cookie 存在有效期，失效后需重新获取
- 请勿将含真实 Cookie 的脚本提交到公开仓库（本仓库脚本默认从环境变量读取，不硬编码凭据）
- 点击/分享/扫描类任务已支持自动完成（通过 `task_center.finish` 接口），开通会员/学生认证/邀请好友等任务需手动操作
- 建议每日执行一次，频繁请求可能触发风控
- Telegram 机器人如需在群聊中接收无 @ 的消息，必须关闭 Privacy Mode
- QQ 机器人需要在 NapCat 中配置反向 WebSocket

## 依赖

- Python 3.8+
- `requests`
- `pycryptodome`
- `python-telegram-bot`
- `websockets`
