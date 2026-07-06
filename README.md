# QL-WPS · WPS 会员中心自动签到 & 任务

青龙面板（QingLong）/ 本地均可使用的 WPS 会员中心每日签到与任务自动化脚本。

通过逆向分析 WPS 活动页面的前端加密逻辑与任务接口，实现**纯接口**完成签到和多种类型任务，无需浏览器自动化，稳定高效。

## 功能特性

- **每日签到** — 自动完成 WPS 会员中心每日签到，领取积分与勋章
- **自适应任务引擎** — 按任务类型（task_event）+ 状态（task_status）自动选择完成策略，不硬编码任务ID，任务变更后仍能自适应处理
- **多类型任务支持** — click/share/scan 直接 finish 完成、browse 浏览任务完整流程、exchange_traffic 换量任务自动访问
- **待领奖自动领取** — 检测到待领奖状态（toReceive）自动领取奖励
- **任务总览** — 列出全部任务及完成状态，对无法自动完成的任务给出提示
- **多账号** — 支持环境变量配置多个账号，循环执行
- **青龙适配** — 通过环境变量 `WPS_COOKIE` 注入凭据，适配青龙面板定时任务

## 已验证能力

| 任务类型 | 策略 | 状态 | 说明 |
| --- | --- | --- | --- |
| 签到 | RSA+AES加密 | ✅ 可用 | 已实测签到成功 |
| click（点击） | task_center.finish + reward | ✅ 可用 | 14个click任务实测全部完成 |
| share（分享） | task_center.finish + reward | ✅ 可用 | 实测完成 |
| scan（扫描） | task_center.finish + reward | ✅ 可用 | 同click机制 |
| browse（浏览） | start → task_info → 等待 → finish → reward | ✅ 可用 | 全链路实测通过 |
| exchange_traffic（换量） | start → 访问jump_url → finish → reward | ⚠️ 部分 | 需目标App内操作，纯接口可能失败 |
| toReceive（待领奖） | 直接 reward | ✅ 可用 | 自动检测并领取 |
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

### 3. 运行

```bash
python3 wps_auto.py
```

## 获取 Cookie

1. 浏览器访问 [WPS 个人中心](https://account.wps.cn) 并登录
2. 按 `F12` 打开开发者工具，切换到 **Network** 标签
3. 刷新页面，点击任意一个请求
4. 在 **Request Headers** 中找到 `Cookie` 字段，复制完整值

> Cookie 中关键字段为 `wps_sid`、`kso_sid`、`csrf`、`uid`，缺一不可。

## 青龙面板部署

1. **添加脚本**：在青龙面板「脚本管理」中拉取本仓库，或手动上传 `wps_auto.py`
2. **安装依赖**：在「依赖管理 → Python」中添加 `requests`、`pycryptodome`
3. **配置环境变量**：在「环境变量」中新增
   - 名称：`WPS_COOKIE`
   - 值：你的 WPS 账号 Cookie（多账号换行或用 `&` 分隔）
4. **创建定时任务**：
   - 命令：`task wps_auto.py`（青龙）或 `python3 wps_auto.py`
   - 定时规则：`30 8 * * *`（每天 8:30 执行）

## 配置项

| 配置 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 账号 Cookie | `WPS_COOKIE` | 空 | 多账号用换行或 `&` 分隔 |
| 是否签到 | — | `True` | 修改脚本 `DO_SIGN_IN` |
| 浏览等待冗余 | — | `3` 秒 | 修改脚本 `BROWSE_EXTRA_WAIT` |
| finish后等待 | — | `3` 秒 | 修改脚本 `FINISH_DELAY`（服务端处理延迟） |
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

## 文件说明

```
QL-WPS/
├── wps_auto.py       # 主脚本
├── requirements.txt  # Python 依赖
└── README.md         # 说明文档
```

## 注意事项

- 本脚本仅供学习交流使用，请勿用于商业用途
- Cookie 存在有效期，失效后需重新获取
- 请勿将含真实 Cookie 的脚本提交到公开仓库（本仓库脚本默认从环境变量读取，不硬编码凭据）
- 点击/分享/扫描类任务已支持自动完成（通过 `task_center.finish` 接口），开通会员/学生认证/邀请好友等任务需手动操作
- 建议每日执行一次，频繁请求可能触发风控

## 依赖

- Python 3.7+
- `requests`
- `pycryptodome`
