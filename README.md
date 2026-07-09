# QL-WPS · WPS 会员中心自动脚本

WPS 会员中心自动签到、任务、抽奖、推送脚本，适配青龙面板或本地定时任务。

QQ 群交互控制由 [Hayfan-wu/QL-Bot](https://github.com/Hayfan-wu/QL-Bot) 提供。`QL-Bot` 只做机器人框架，不保存 WPS 项目配置；WPS 的路径、脚本路径、青龙凭据都放在本仓库自己的 `.env` 中。

## 功能

- 每日签到（RSA + AES 加密）
- 自适应任务完成（click / share / scan / browse / exchange_traffic / 待领奖）
- 自动九宫格抽奖
- WXPusher 微信推送
- 多账号支持（环境变量 `WPS_COOKIE` 中用换行或 `&` 分隔）

## 依赖

```bash
pip install requests pycryptodome
```

## 配置

复制模板：

```bash
cd /opt/QL-WPS
cp .env.example .env
nano .env
```

推荐配置：

```bash
WPS_PROJECT_DIR=/opt/QL-WPS
WPS_SCRIPT_PATH=/opt/QL-WPS/wps_auto.py

QL_URL=http://127.0.0.1:5700
QL_CLIENT_ID=你的WPS项目青龙ClientID
QL_CLIENT_SECRET=你的WPS项目青龙ClientSecret

WXPUSHER_APP_TOKEN=
WXPUSHER_UID=
```

`WPS_COOKIE` 不需要手动填写到 `.env`。通过 QQ 机器人发送 `WPS登录` 并粘贴 Cookie 后，机器人会自动把 `WPS_COOKIE` 写入上面配置的青龙面板。

本地临时运行也可以直接导出环境变量：

```bash
export WPS_COOKIE="你的WPS Cookie"
export WXPUSHER_APP_TOKEN="可选"
export WXPUSHER_UID="可选"
```

## 运行

```bash
python3 wps_auto.py
```

## 青龙面板

1. 上传 `wps_auto.py` 到青龙脚本目录
2. 在青龙「依赖管理」安装 `requests`、`pycryptodome`
3. 通过 QQ 机器人 `WPS登录` 自动写入环境变量 `WPS_COOKIE`
4. 创建定时任务：`task wps_auto.py`，建议每天执行一次

## 与 QL-Bot 配合

推荐目录结构：

```bash
/opt/QL-Bot
/opt/QL-WPS
```

`QL-Bot/.env` 只配置 QQ 机器人、NapCat、WebSocket 等框架参数，不配置 `WPS_PROJECT_DIR`、`WPS_SCRIPT_PATH`、`QL_CLIENT_ID`、`QL_CLIENT_SECRET`。

`QL-WPS` 自带 QQ 控制插件，插件放在 `bot_plugins/wps.py`。`QL-Bot` 启动时会自动扫描 `/opt/*/bot_plugins/` 并加载插件，所以以后新增或维护业务项目时，不需要改 `QL-Bot/.env`。

之后通过 QQ 群 `@机器人 WPS登录` 提交 Cookie，`@机器人 WPS执行` 运行签到。

## 文件说明

```
QL-WPS/
├── wps_auto.py       # 主脚本
├── bot_plugins/
│   └── wps.py        # QQ 机器人控制插件
├── .env.example      # 项目环境变量模板
├── .gitignore
└── README.md
```
