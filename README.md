# QL-WPS · WPS 会员中心自动脚本

WPS 会员中心自动签到、任务、抽奖、推送脚本，适配青龙面板或本地定时任务。

QQ 群交互控制请移步：[Hayfan-wu/QL-Bot](https://github.com/Hayfan-wu/QL-Bot)

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
3. 添加环境变量 `WPS_COOKIE`
4. 创建定时任务：`task wps_auto.py`，建议每天执行一次

## 与 QQ 机器人配合使用

```bash
cd /opt
git clone https://github.com/Hayfan-wu/QL-WPS.git
git clone https://github.com/Hayfan-wu/QL-Bot.git

# QL-WPS 项目自己的 .env
cp /opt/QL-WPS/.env.example /opt/QL-WPS/.env
nano /opt/QL-WPS/.env
# 配置：QL_URL, QL_CLIENT_ID, QL_CLIENT_SECRET, WPS_SCRIPT_PATH

# QL-Bot 的 .env 中只需配置项目路径
WPS_PROJECT_DIR=/opt/QL-WPS
```

之后通过 QQ 群 `@机器人 WPS登录` 提交 Cookie，`@机器人 WPS执行` 运行签到。

## 文件说明

```
QL-WPS/
├── wps_auto.py     # 主脚本
├── .env.example    # 项目级配置模板
├── .gitignore
└── README.md
```
