# -*- coding: utf-8 -*-
"""WPS 账号管理插件"""

import re

from bot.plugins.base import Plugin
from bot.ql_api import ql
from bot.session import sessions
from bot.utils import Log


WPS_ENV_PREFIX = 'WPS_COOKIE_'


def get_env_name(account):
    return f'{WPS_ENV_PREFIX}{account}'


def find_env(account):
    env_name = get_env_name(account)
    envs = ql.list_envs(env_name)
    for env in envs:
        if env.get('name') == env_name:
            return env
    return None


def list_accounts():
    envs = ql.list_envs(WPS_ENV_PREFIX)
    accounts = []
    for env in envs:
        name = env.get('name', '')
        if name.startswith(WPS_ENV_PREFIX):
            accounts.append(name[len(WPS_ENV_PREFIX):])
    return accounts


def save_cookie(account, cookie):
    env_name = get_env_name(account)
    existing = find_env(account)
    if existing:
        ql.update_env(existing['id'], env_name, cookie, remarks=f'WPS账号 {account}')
        return '更新'
    else:
        ql.create_env(env_name, cookie, remarks=f'WPS账号 {account}')
        return '新增'


def delete_cookie(account):
    existing = find_env(account)
    if existing:
        ql.delete_env(existing['id'])
        return True
    return False


def parse_login_args(text):
    """解析登录参数
    支持：WPS登录 账号1 cookie
    """
    text = re.sub(r'^账号[:：]wps\s*登录\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^wps\s*登录\s*', '', text, flags=re.IGNORECASE)
    text = text.strip()
    parts = text.split(' ', 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    elif len(parts) == 1:
        return parts[0].strip(), None
    return None, None


class WpsPlugin(Plugin):
    name = 'wps'
    commands = [
        re.compile(r'^账号[:：]wps\s*登录', re.IGNORECASE),
        re.compile(r'^wps\s*登录', re.IGNORECASE),
        re.compile(r'^账号[:：]wps\s*查询', re.IGNORECASE),
        re.compile(r'^wps\s*查询', re.IGNORECASE),
        re.compile(r'^账号[:：]wps\s*管理', re.IGNORECASE),
        re.compile(r'^wps\s*管理', re.IGNORECASE),
        re.compile(r'^账号[:：]wps\s*列表', re.IGNORECASE),
        re.compile(r'^wps\s*列表', re.IGNORECASE),
    ]

    def handle(self, text, sender_id, group_id=None):
        session = sessions.get(sender_id, group_id)

        # 帮助
        if text.lower() in ['帮助', '菜单', 'help']:
            return self.help_text()

        # 登录命令
        if self._is_login(text):
            return self._handle_login(text, sender_id, group_id)

        # 查询命令
        if self._is_query(text):
            return self._handle_query(text)

        # 管理命令
        if self._is_manage(text):
            return self._handle_manage(text)

        # 列表命令
        if self._is_list(text):
            return self._handle_list()

        return '未知命令，发送「帮助」查看命令列表'

    def _is_login(self, text):
        return bool(re.search(r'^账号[:：]wps\s*登录', text, re.IGNORECASE) or
                    re.search(r'^wps\s*登录', text, re.IGNORECASE))

    def _is_query(self, text):
        return bool(re.search(r'^账号[:：]wps\s*查询', text, re.IGNORECASE) or
                    re.search(r'^wps\s*查询', text, re.IGNORECASE))

    def _is_manage(self, text):
        return bool(re.search(r'^账号[:：]wps\s*管理', text, re.IGNORECASE) or
                    re.search(r'^wps\s*管理', text, re.IGNORECASE))

    def _is_list(self, text):
        return bool(re.search(r'^账号[:：]wps\s*列表', text, re.IGNORECASE) or
                    re.search(r'^wps\s*列表', text, re.IGNORECASE))

    def _handle_login(self, text, sender_id, group_id):
        account, cookie = parse_login_args(text)

        # 一键登录
        if account and cookie:
            try:
                action = save_cookie(account, cookie)
                sessions.clear(sender_id, group_id)
                return f'✅ {action}账号 [{account}] 成功，已保存到青龙环境变量'
            except Exception as e:
                return f'❌ 保存失败: {str(e)}'

        # 已输入账号备注，等待 cookie
        if account:
            sessions.set(sender_id, group_id, 'wps', {'step': 'waiting_cookie', 'account': account})
            return f'请输入账号 [{account}] 的 Cookie'

        # 等待输入账号备注
        sessions.set(sender_id, group_id, 'wps', {'step': 'waiting_account'})
        return '请输入账号备注，例如：账号1'

    def _handle_query(self, text):
        text = re.sub(r'^账号[:：]wps\s*查询\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^wps\s*查询\s*', '', text, flags=re.IGNORECASE)
        account = text.strip()
        if not account:
            return '格式错误，正确格式：WPS查询 账号备注'
        env = find_env(account)
        if not env:
            return f'未找到账号 [{account}]，请先执行 WPS登录'
        return (
            f'账号 [{account}] 状态\n'
            f'─────────────────\n'
            f'状态：已保存到青龙环境变量\n'
            f'变量名：{env.get("name")}\n'
            f'备注：{env.get("remarks", "")}\n'
            f'更新时间：{env.get("timestamp", "未知")}\n\n'
            f'青龙定时任务执行 WPS 签到后，会自动推送积分结果到 QQ。'
        )

    def _handle_manage(self, text):
        text = re.sub(r'^账号[:：]wps\s*管理\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^wps\s*管理\s*', '', text, flags=re.IGNORECASE)
        text = text.strip()
        if text.startswith('登出'):
            account = text[2:].strip()
            if not account:
                return '格式错误，正确格式：WPS管理 登出 账号备注'
            if delete_cookie(account):
                return f'✅ 账号 [{account}] 已登出，Cookie 已删除'
            return f'未找到账号 [{account}]'
        return '格式错误，正确格式：WPS管理 登出 账号备注'

    def _handle_list(self):
        accounts = list_accounts()
        if accounts:
            return '当前 WPS 账号列表：\n' + '\n'.join([f'• {a}' for a in accounts])
        return '当前没有保存任何 WPS 账号'

    def help_text(self):
        return (
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
            '   @机器人 WPS管理 登出 账号备注'
        )
