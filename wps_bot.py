#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WPS QQ 机器人服务端
==================
基于 NapCatQQ 反向 WebSocket 接收消息，实现 WPS 账号的交互式登录、查询、管理。

交互流程（群内）：
1. 用户 @机器人 账号:wps 登录
2. 机器人回复：请输入账号备注
3. 用户发送：账号1
4. 机器人回复：请输入账号 [账号1] 的 Cookie
5. 用户发送 Cookie
6. 机器人保存到青龙环境变量并回复成功

命令列表：
- 账号:wps 登录 / WPS登录 / wps登录
- WPS查询 账号备注 / 账号:wps 查询 账号备注
- WPS管理 登出 账号备注 / 账号:wps 管理 登出 账号备注
- WPS列表 / 账号:wps 列表
- 帮助 / 菜单
"""

import os
import re
import json
import asyncio
import requests
import websockets
from datetime import datetime
from urllib.parse import urlparse

# ======================== 配置区 ========================

# 机器人监听配置（与 NapCat 反向 WS 对应）
WS_HOST = os.getenv('WS_HOST', '0.0.0.0')
WS_PORT = int(os.getenv('WS_PORT', '8080'))
WS_PATH = os.getenv('WS_PATH', '/onebot/v11/ws/')
WS_TOKEN = os.getenv('WS_TOKEN', '')  # 反向 WS 鉴权 Token，与 NapCat 中配置一致

# NapCat HTTP API 配置（用于回复消息）
NAPCAT_API = os.getenv('NAPCAT_API', 'http://127.0.0.1:3000')
NAPCAT_TOKEN = os.getenv('NAPCAT_TOKEN', '')

# 机器人自己的 QQ 号（用于识别群消息中的 @）
QQ_BOT_QQ = os.getenv('QQ_BOT_QQ', '')

# 青龙面板 Open API 配置
QL_URL = os.getenv('QL_URL', 'http://127.0.0.1:5700')
QL_CLIENT_ID = os.getenv('QL_CLIENT_ID', '')
QL_CLIENT_SECRET = os.getenv('QL_CLIENT_SECRET', '')

# 允许的 QQ 管理员，多个用逗号分隔，留空表示不限制
ADMIN_QQ = os.getenv('ADMIN_QQ', '')

# WPS 环境变量名前缀
WPS_ENV_PREFIX = 'WPS_COOKIE_'

# 会话超时时间（秒）
SESSION_TIMEOUT = 300

# ======================== 日志 ========================

class Log:
    @staticmethod
    def _ts():
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def info(msg):
        print(f'[{Log._ts()}] [INFO] {msg}')

    @staticmethod
    def ok(msg):
        print(f'[{Log._ts()}] [OK] {msg}')

    @staticmethod
    def fail(msg):
        print(f'[{Log._ts()}] [FAIL] {msg}')


# ======================== 青龙 API 封装 ========================

class QingLongAPI:
    def __init__(self, base_url, client_id, client_secret):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None

    def _get_token(self):
        url = f'{self.base_url}/open/auth/token'
        params = {'client_id': self.client_id, 'client_secret': self.client_secret}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get('code') == 200:
            self.token = data['data']['token']
            return self.token
        raise Exception(f'青龙登录失败: {data}')

    def _headers(self):
        if not self.token:
            self._get_token()
        return {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}

    def list_envs(self, search_value=''):
        url = f'{self.base_url}/open/envs'
        params = {'searchValue': search_value} if search_value else {}
        r = requests.get(url, headers=self._headers(), params=params, timeout=10)
        data = r.json()
        if data.get('code') == 200:
            return data.get('data', [])
        raise Exception(f'获取环境变量失败: {data}')

    def create_env(self, name, value, remarks=''):
        url = f'{self.base_url}/open/envs'
        payload = {'name': name, 'value': value, 'remarks': remarks}
        r = requests.post(url, headers=self._headers(), json=payload, timeout=10)
        data = r.json()
        if data.get('code') == 200:
            return data.get('data')
        raise Exception(f'创建环境变量失败: {data}')

    def update_env(self, env_id, name, value, remarks=''):
        url = f'{self.base_url}/open/envs'
        payload = {'id': env_id, 'name': name, 'value': value, 'remarks': remarks}
        r = requests.put(url, headers=self._headers(), json=payload, timeout=10)
        data = r.json()
        if data.get('code') == 200:
            return data.get('data')
        raise Exception(f'更新环境变量失败: {data}')

    def delete_env(self, env_id):
        url = f'{self.base_url}/open/envs'
        r = requests.delete(url, headers=self._headers(), json=[env_id], timeout=10)
        data = r.json()
        if data.get('code') == 200:
            return True
        raise Exception(f'删除环境变量失败: {data}')


ql = QingLongAPI(QL_URL, QL_CLIENT_ID, QL_CLIENT_SECRET)


# ======================== QQ 消息发送 ========================

def send_qq_message(message, user_id=None, group_id=None):
    if not NAPCAT_API:
        Log.fail('未配置 NAPCAT_API，无法回复消息')
        return False
    headers = {'Content-Type': 'application/json'}
    if NAPCAT_TOKEN:
        headers['Authorization'] = f'Bearer {NAPCAT_TOKEN}'
    if group_id:
        url = f'{NAPCAT_API}/send_group_msg'
        payload = {'group_id': int(group_id), 'message': message}
    elif user_id:
        url = f'{NAPCAT_API}/send_private_msg'
        payload = {'user_id': int(user_id), 'message': message}
    else:
        Log.fail('未指定 user_id 或 group_id')
        return False
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        Log.info(f'发送消息结果: {r.json()}')
        return True
    except Exception as e:
        Log.fail(f'发送消息失败: {e}')
        return False


# ======================== WPS 环境变量操作 ========================

def get_wps_env_name(account_name):
    return f'{WPS_ENV_PREFIX}{account_name}'


def find_wps_env(account_name):
    env_name = get_wps_env_name(account_name)
    envs = ql.list_envs(env_name)
    for env in envs:
        if env.get('name') == env_name:
            return env
    return None


def list_wps_accounts():
    envs = ql.list_envs(WPS_ENV_PREFIX)
    accounts = []
    for env in envs:
        name = env.get('name', '')
        if name.startswith(WPS_ENV_PREFIX):
            accounts.append(name[len(WPS_ENV_PREFIX):])
    return accounts


def save_wps_cookie(account_name, cookie):
    env_name = get_wps_env_name(account_name)
    existing = find_wps_env(account_name)
    if existing:
        ql.update_env(existing['id'], env_name, cookie, remarks=f'WPS账号 {account_name}')
        return '更新'
    else:
        ql.create_env(env_name, cookie, remarks=f'WPS账号 {account_name}')
        return '新增'


def delete_wps_cookie(account_name):
    existing = find_wps_env(account_name)
    if existing:
        ql.delete_env(existing['id'])
        return True
    return False


# ======================== 会话状态管理 ========================

user_sessions = {}


def get_session_key(sender_id, group_id=None):
    return f'{sender_id}_{group_id or "private"}'


def set_session(sender_id, group_id, step, account=None):
    key = get_session_key(sender_id, group_id)
    user_sessions[key] = {
        'step': step,
        'account': account,
        'time': datetime.now().timestamp()
    }


def get_session(sender_id, group_id=None):
    key = get_session_key(sender_id, group_id)
    session = user_sessions.get(key)
    if not session:
        return None
    # 超时清理
    if datetime.now().timestamp() - session.get('time', 0) > SESSION_TIMEOUT:
        del user_sessions[key]
        return None
    return session


def clear_session(sender_id, group_id=None):
    key = get_session_key(sender_id, group_id)
    if key in user_sessions:
        del user_sessions[key]


# ======================== 命令处理 ========================

def normalize_text(text, bot_qq):
    """清理消息文本：移除 @机器人 和 CQ 码"""
    if not text:
        return ''
    # 移除 CQ:at 码
    text = re.sub(r'\[CQ:at,qq=\d+\]', ' ', text)
    # 移除 @机器人QQ
    if bot_qq:
        text = re.sub(rf'@{bot_qq}\s*', ' ', text)
        text = re.sub(rf'@{bot_qq}', ' ', text)
    # 替换全角空格
    text = text.replace('\u3000', ' ')
    # 合并多个空格
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def is_login_command(text):
    """判断是否为登录命令"""
    patterns = [
        r'^账号[:：]wps\s*登录$',
        r'^wps\s*登录$',
        r'^WPS\s*登录$',
        r'^账号[:：]wps\s*登录\s+',
        r'^wps\s*登录\s+',
        r'^WPS\s*登录\s+',
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def is_query_command(text):
    patterns = [r'^账号[:：]wps\s*查询', r'^wps\s*查询', r'^WPS\s*查询']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_manage_command(text):
    patterns = [r'^账号[:：]wps\s*管理', r'^wps\s*管理', r'^WPS\s*管理']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_list_command(text):
    patterns = [r'^账号[:：]wps\s*列表', r'^wps\s*列表', r'^WPS\s*列表']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_help_command(text):
    patterns = [r'^帮助$', r'^菜单$', r'^help$', r'^help\s+']
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def send_help(sender_id, group_id=None):
    msg = (
        '📋 WPS 机器人命令列表\n'
        '─────────────────\n'
        '1️⃣ 登录账号（交互式）：\n'
        '   @机器人 账号:wps 登录\n'
        '   然后按提示输入账号备注和 Cookie\n\n'
        '2️⃣ 一键登录（直接带参数）：\n'
        '   @机器人 WPS登录 账号备注 Cookie内容\n\n'
        '3️⃣ 查询账号：\n'
        '   @机器人 WPS查询 账号备注\n\n'
        '4️⃣ 列出账号：\n'
        '   @机器人 WPS列表\n\n'
        '5️⃣ 登出账号：\n'
        '   @机器人 WPS管理 登出 账号备注\n\n'
        '💡 提示：Cookie 获取方法见 README'
    )
    send_qq_message(msg, user_id=sender_id, group_id=group_id)


def parse_login_args(text):
    """解析登录参数，返回 (account, cookie)
    支持格式：
    - WPS登录 账号1 cookie
    - 账号:wps 登录 账号1 cookie
    """
    # 移除命令前缀
    text = re.sub(r'^账号[:：]wps\s*登录\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^wps\s*登录\s*', '', text, flags=re.IGNORECASE)
    text = text.strip()
    parts = text.split(' ', 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    elif len(parts) == 1:
        return parts[0].strip(), None
    return None, None


def handle_command(raw_text, sender_id, group_id=None):
    text = normalize_text(raw_text, QQ_BOT_QQ)
    Log.info(f'处理命令: sender={sender_id}, group={group_id}, text={text}')

    if not text:
        return

    # 权限检查
    if ADMIN_QQ and str(sender_id) not in ADMIN_QQ.split(','):
        send_qq_message('你没有权限使用此机器人', user_id=sender_id, group_id=group_id)
        return

    session = get_session(sender_id, group_id)

    # 帮助命令
    if is_help_command(text):
        send_help(sender_id, group_id)
        return

    # 登录命令
    if is_login_command(text):
        account, cookie = parse_login_args(text)
        if account and cookie:
            # 一键登录
            try:
                action = save_wps_cookie(account, cookie)
                send_qq_message(f'✅ {action}账号 [{account}] 成功，已保存到青龙环境变量', user_id=sender_id, group_id=group_id)
            except Exception as e:
                send_qq_message(f'❌ 保存失败: {str(e)}', user_id=sender_id, group_id=group_id)
            clear_session(sender_id, group_id)
        elif account:
            # 等待输入 cookie
            set_session(sender_id, group_id, 'waiting_cookie', account)
            send_qq_message(f'请输入账号 [{account}] 的 Cookie', user_id=sender_id, group_id=group_id)
        else:
            # 等待输入账号备注
            set_session(sender_id, group_id, 'waiting_account')
            send_qq_message('请输入账号备注，例如：账号1', user_id=sender_id, group_id=group_id)
        return

    # 处理会话状态
    if session:
        step = session.get('step')
        if step == 'waiting_account':
            account = text.strip()
            if not account:
                send_qq_message('账号备注不能为空，请重新输入', user_id=sender_id, group_id=group_id)
                return
            set_session(sender_id, group_id, 'waiting_cookie', account)
            send_qq_message(f'请输入账号 [{account}] 的 Cookie', user_id=sender_id, group_id=group_id)
            return
        elif step == 'waiting_cookie':
            account = session.get('account', 'default')
            cookie = text.strip()
            if not cookie:
                send_qq_message('Cookie 不能为空，请重新输入', user_id=sender_id, group_id=group_id)
                return
            try:
                action = save_wps_cookie(account, cookie)
                send_qq_message(f'✅ {action}账号 [{account}] 成功，已保存到青龙环境变量', user_id=sender_id, group_id=group_id)
            except Exception as e:
                send_qq_message(f'❌ 保存失败: {str(e)}', user_id=sender_id, group_id=group_id)
            clear_session(sender_id, group_id)
            return

    # 查询命令
    if is_query_command(text):
        text = re.sub(r'^账号[:：]wps\s*查询\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^wps\s*查询\s*', '', text, flags=re.IGNORECASE)
        account = text.strip()
        if not account:
            send_qq_message('格式错误，正确格式：WPS查询 账号备注', user_id=sender_id, group_id=group_id)
            return
        env = find_wps_env(account)
        if not env:
            send_qq_message(f'未找到账号 [{account}]，请先执行 WPS登录', user_id=sender_id, group_id=group_id)
            return
        msg = (
            f'账号 [{account}] 状态\n'
            f'─────────────────\n'
            f'状态：已保存到青龙环境变量\n'
            f'变量名：{env.get("name")}\n'
            f'备注：{env.get("remarks", "")}\n'
            f'更新时间：{env.get("timestamp", "未知")}\n\n'
            f'青龙定时任务执行 WPS 签到后，会自动推送积分结果到 QQ。'
        )
        send_qq_message(msg, user_id=sender_id, group_id=group_id)
        return

    # 管理命令
    if is_manage_command(text):
        text = re.sub(r'^账号[:：]wps\s*管理\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^wps\s*管理\s*', '', text, flags=re.IGNORECASE)
        text = text.strip()
        if text.startswith('登出'):
            account = text[2:].strip()
            if not account:
                send_qq_message('格式错误，正确格式：WPS管理 登出 账号备注', user_id=sender_id, group_id=group_id)
                return
            if delete_wps_cookie(account):
                send_qq_message(f'✅ 账号 [{account}] 已登出，Cookie 已删除', user_id=sender_id, group_id=group_id)
            else:
                send_qq_message(f'未找到账号 [{account}]', user_id=sender_id, group_id=group_id)
        else:
            send_qq_message('格式错误，正确格式：WPS管理 登出 账号备注', user_id=sender_id, group_id=group_id)
        return

    # 列表命令
    if is_list_command(text):
        accounts = list_wps_accounts()
        if accounts:
            reply = '当前 WPS 账号列表：\n' + '\n'.join([f'• {a}' for a in accounts])
        else:
            reply = '当前没有保存任何 WPS 账号'
        send_qq_message(reply, user_id=sender_id, group_id=group_id)
        return

    # 未知命令
    send_qq_message('未知命令，发送「帮助」查看命令列表', user_id=sender_id, group_id=group_id)


# ======================== WebSocket 服务 ========================

async def handle_ws(websocket, path):
    Log.info(f'NapCat 已连接: {websocket.remote_address}')
    try:
        async for message in websocket:
            Log.info(f'收到原始消息: {message}')
            try:
                data = json.loads(message)
                # 处理鉴权心跳等
                post_type = data.get('post_type')
                if post_type != 'message':
                    continue

                raw_msg = data.get('raw_message', '')
                sender = data.get('sender', {})
                sender_id = sender.get('user_id')
                group_id = data.get('group_id')
                message_type = data.get('message_type', '')

                # 群消息必须 @ 机器人才响应
                if message_type == 'group':
                    if not QQ_BOT_QQ:
                        Log.warn('未配置 QQ_BOT_QQ，无法识别群 @ 消息')
                        continue
                    if QQ_BOT_QQ not in raw_msg and f'[CQ:at,qq={QQ_BOT_QQ}]' not in raw_msg:
                        Log.info('群消息未 @ 机器人，忽略')
                        continue

                handle_command(raw_msg, sender_id, group_id)
            except Exception as e:
                Log.fail(f'处理消息异常: {e}')
    except websockets.exceptions.ConnectionClosed as e:
        Log.info(f'NapCat 断开连接: {e}')


async def main():
    Log.ok(f'启动 WPS QQ 机器人，监听 ws://{WS_HOST}:{WS_PORT}{WS_PATH}')
    async with websockets.serve(handle_ws, WS_HOST, WS_PORT, path=WS_PATH):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
