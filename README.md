# QQ 机器人插件化框架 · 以 WPS 为例

> 一个基于 NapCatQQ 反向 WebSocket 的通用 QQ 机器人框架。后续新增项目只需在 `bot/plugins/` 下写一个插件文件即可，不需要重复部署机器人服务。

## 架构设计

```text
┌─────────────┐     反向 WS      ┌──────────────┐     插件分发      ┌─────────────┐
│   QQ 用户    │ ───────────────> │   QQ 机器人核心  │ ─────────────> │ WPS/其他插件  │
│ （群里 @机器人）│                  │  main.py     │                │             │
└─────────────┘                  └──────────────┘                └──────┬──────┘
                                                                         │
                                                                         v
                                                                  ┌─────────────┐
                                                                  │ 青龙 Open API │
                                                                  │ 环境变量管理  │
                                                                  └─────────────┘
```

## 目录结构

```text
.
├── main.py                 # 机器人启动入口
├── wps_auto.py             # WPS 自动签到脚本
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── wps-bot.service         # systemd 服务模板
├── bot/
│   ├── config.py           # 配置管理
│   ├── core.py             # 核心：WS 服务、插件加载、消息分发
│   ├── utils.py            # 日志、消息发送、文本清理
│   ├── ql_api.py           # 青龙 API 封装
│   ├── session.py          # 用户会话状态管理
│   └── plugins/
│       ├── base.py         # 插件基类
│       ├── wps.py          # WPS 账号管理插件（示例）
│       └── example.py      # 新增插件参考示例
```

## 快速部署

### 1. 下载代码

```bash
mkdir -p /opt/qq-bot
cd /opt/qq-bot

curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/main.py
curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/wps_auto.py
curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/requirements.txt
curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/.env.example
curl -O https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/wps-bot.service

mkdir -p bot/plugins
curl -o bot/__init__.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/__init__.py
curl -o bot/config.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/config.py
curl -o bot/core.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/core.py
curl -o bot/utils.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/utils.py
curl -o bot/ql_api.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/ql_api.py
curl -o bot/session.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/session.py
curl -o bot/plugins/__init__.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/plugins/__init__.py
curl -o bot/plugins/base.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/plugins/base.py
curl -o bot/plugins/wps.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/plugins/wps.py
curl -o bot/plugins/example.py https://raw.githubusercontent.com/Hayfan-wu/QL-WPS/main/bot/plugins/example.py
```

### 2. 安装依赖

```bash
pip install requests pycryptodome websockets --break-system-packages
```

### 3. 配置环境变量

```bash
cp .env.example .env
nano .env
```

关键配置：

```text
QQ_BOT_QQ=机器人QQ号
NAPCAT_API=http://服务器IP:3000
NAPCAT_TOKEN=napcat_token
QL_URL=http://127.0.0.1:5700
QL_CLIENT_ID=青龙ClientID
QL_CLIENT_SECRET=青龙ClientSecret
ADMIN_QQ=你的QQ号
```

### 4. 配置 NapCat 反向 WebSocket

NapCat WebUI → 网络配置 → OneBot 11 → 新建 **Websocket客户端**：

```text
名称：qq-bot
启用：是
主机：127.0.0.1
端口：8080
路径：/onebot/v11/ws/
消息上报格式：string
```

重启 NapCat：

```bash
docker restart napcat
```

### 5. 启动机器人

```bash
export $(cat .env | grep -v '^#' | xargs)
nohup python3 main.py > bot.log 2>&1 &
```

查看日志：

```bash
tail -f bot.log
```

## 交互流程

### WPS 登录

```text
用户：@机器人 账号:wps 登录
机器人：请输入账号备注，例如：账号1
用户：账号1
机器人：请输入账号 [账号1] 的 Cookie
用户：sid=xxxxx;wpsid=xxxxx
机器人：✅ 新增账号 [账号1] 成功，已保存到青龙环境变量
```

### 其他命令

```text
@机器人 WPS登录 账号1 cookie内容      # 一键登录
@机器人 WPS查询 账号1                 # 查询账号状态
@机器人 WPS列表                       # 列出所有账号
@机器人 WPS管理 登出 账号1            # 删除账号
@机器人 帮助                          # 显示命令列表
```

## 如何新增项目（核心）

不需要改动机器人核心代码，只需在 `bot/plugins/` 下新建一个 Python 文件。

### 示例：新增一个「天气查询」插件

创建 `bot/plugins/weather.py`：

```python
import re
import requests
from bot.plugins.base import Plugin


class WeatherPlugin(Plugin):
    name = 'weather'
    commands = [
        '天气',
        re.compile(r'^天气\s+', re.IGNORECASE),
    ]

    def handle(self, text, sender_id, group_id=None):
        city = text.replace('天气', '').strip()
        if not city:
            return '请输入城市，例如：天气 北京'
        # 这里调用天气 API
        return f'{city} 今天晴，25℃'
```

重启机器人后，群里发送 `@机器人 天气 北京` 就会返回结果。

### 插件开发规范

1. 继承 `Plugin` 基类
2. 设置 `name`（唯一标识）和 `commands`（触发前缀）
3. 实现 `handle(text, sender_id, group_id)` 方法
4. 返回字符串即自动回复，返回 None 则不回复
5. 需要多轮交互时，使用 `bot.session.sessions` 保存会话状态

## WPS 签到脚本

`wps_auto.py` 是青龙定时任务脚本，会读取所有 `WPS_COOKIE_账号备注` 环境变量执行签到，并通过 QQ 推送结果。

青龙环境变量配置：

```text
QQ_BOT_API=http://服务器IP:3000/send_group_msg
QQ_BOT_TOKEN=napcat_token
QQ_GROUP_ID=群号
```

定时任务：

```text
命令：task wps_auto.py
定时：30 8 * * *
```

## 常见问题

### 群里 @ 机器人无反应

1. 检查 `.env` 中 `QQ_BOT_QQ` 是否配置正确
2. 检查 NapCat 是否已连接：`tail -f bot.log` 应显示 `NapCat 已连接`
3. 检查 NapCat 中是否配置了 **Websocket客户端** 指向 `127.0.0.1:8080`
4. 检查 `ADMIN_QQ` 是否限制了发送者

### 插件加载失败

```bash
tail -f bot.log
```

查看具体插件加载错误，通常是文件语法问题或依赖缺失。

### Cookie 保存失败

1. 检查青龙应用权限是否包含「环境变量」
2. 检查 `QL_CLIENT_ID` 和 `QL_CLIENT_SECRET` 是否正确

## 安全提醒

- 使用 QQ 小号跑机器人
- `ADMIN_QQ` 建议只填自己的 QQ 号
- Cookie 等敏感信息不要发在公开群
- 青龙应用只授予「环境变量」权限
