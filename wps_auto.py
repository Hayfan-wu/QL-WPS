#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WPS 会员中心 自动签到 & 任务完成脚本
=====================================
功能：
  1. 每日签到（RSA + AES 加密，已验证可用）
  2. 自动完成「浏览类」任务（浏览福利中心/积分商城等，已验证可用）
  3. 查询并展示所有任务状态
  4. 对无法纯接口完成的任务（点击/分享/开通会员等）给出提示

依赖：
  pip install requests pycryptodome

用法：
  方式一（环境变量，推荐，适配青龙面板）：
    export WPS_COOKIE="cookie1账号1"
    多账号用换行或 & 分隔：
    export WPS_COOKIE="账号1cookie
账号2cookie"
  方式二（直接编辑脚本）：将下方 COOKIE 改为你自己的 WPS 账号 Cookie
  然后运行：python3 wps_auto.py

获取 Cookie 方法：
  浏览器登录 WPS 个人中心（account.wps.cn），F12 -> Network ->
  随便找一个请求，复制 Request Headers 中的 Cookie 值。

说明：
  脚本已通过实际请求迭代验证（签到成功、浏览任务领取奖励成功）。
  签到接口使用 personal-bus.wps.cn/sign_in/v1/sign_in，需先获取 RSA 公钥
  对 AES 密钥加密生成 token，再用 AES-CBC 加密 {user_id, platform} 作为 extra。
  浏览任务通过 task_center.start -> task_info -> 等待 -> task_finish -> reward 完成。
"""

import requests
import json
import time
import random
import string
import base64
import re
import sys
import os
from datetime import datetime

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.Util.Padding import pad

# ======================== 配置区 ========================
# 你的 WPS 账号 Cookie
# 优先从环境变量 WPS_COOKIE 读取（适配青龙面板，多账号用换行或 & 分隔）
# 未设置环境变量时使用下方 DEFAULT_COOKIE（请替换为你自己的 Cookie，留空则不执行）
DEFAULT_COOKIE = ""
COOKIE = os.getenv("WPS_COOKIE", DEFAULT_COOKIE)

# 活动地址（一般无需修改）
ACTIVITY_NUMBER = "HD2025031821201822"
PAGE_NUMBER = "YM2025040908558269"
# 任务中心组件标识（来自 page_info，一般无需修改）
COMPONENT_NUMBER = "ZJ2025040709458367"
COMPONENT_NODE_ID = "FN1744160180RthG"
COMPONENT_TYPE = 35
# URL 中的 filter_params
FILTER_PARAMS = {"position": "ad_rwzx_invite_test", "token": "61b3f3ab86984a191927bfe7748b85a5"}

# 浏览任务等待冗余秒数（在 browse_second 基础上额外等待，确保达标）
BROWSE_EXTRA_WAIT = 3
# 请求间隔（秒），避免风控
REQUEST_INTERVAL = 1.5
# 是否完成浏览任务
DO_BROWSE_TASKS = True
# 是否执行签到
DO_SIGN_IN = True
# ======================== 配置区结束 ========================


# ----------------------- 日志 -----------------------
class Log:
    """简易彩色日志"""
    @staticmethod
    def _ts():
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def info(msg):
        print(f"[{Log._ts()}] [*] {msg}")

    @staticmethod
    def ok(msg):
        print(f"[{Log._ts()}] [+] {msg}")

    @staticmethod
    def warn(msg):
        print(f"[{Log._ts()}] [!] {msg}")

    @staticmethod
    def fail(msg):
        print(f"[{Log._ts()}] [-] {msg}")

    @staticmethod
    def step(msg):
        print(f"\n{'='*52}\n[{Log._ts()}] >>> {msg}\n{'='*52}")


# ----------------------- 加密工具 -----------------------
def gen_aes_key():
    """生成 32 字符 AES 密钥：22 位随机 + 10 位时间戳（复刻前端 di()）"""
    rnd = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(22))
    ts = str(int(time.time()))
    return rnd + ts  # 32 字符


def rsa_encrypt(plain, pem):
    """RSA-PKCS1v1.5 加密（复刻 JSEncrypt encrypt）"""
    key = RSA.import_key(pem)
    cipher = PKCS1_v1_5.new(key)
    return base64.b64encode(cipher.encrypt(plain.encode())).decode()


def aes_encrypt(payload_str, aes_key):
    """AES-CBC 加密（复刻 CryptoJS AES.encrypt，key=32字节, iv=前16字节, Pkcs7）"""
    key = aes_key.encode()          # 32 bytes -> AES-256
    iv = aes_key[:16].encode()      # 16 bytes
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(payload_str.encode(), AES.block_size))
    return base64.b64encode(ct).decode()


# ----------------------- 主类 -----------------------
class WpsAuto:
    SIGN_BASE = "https://personal-bus.wps.cn/sign_in/v1"
    ACT_BASE = "https://personal-act.wps.cn/activity-rubik"

    def __init__(self, cookie):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Referer": f"https://personal-act.wps.cn/rubik2/portal/{ACTIVITY_NUMBER}/{PAGE_NUMBER}",
            "Origin": "https://personal-act.wps.cn",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
        })
        # 注入 cookie
        for item in cookie.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                self.s.cookies.set(k, v, domain=".wps.cn")
        self.user_id = self._extract_uid(cookie)
        self.csrf = self.s.cookies.get("csrf", "")  # account 域 CSRF token

    @staticmethod
    def _extract_uid(cookie):
        m = re.search(r'uid=(\d+)', cookie)
        return int(m.group(1)) if m else 0

    def _sleep(self):
        time.sleep(REQUEST_INTERVAL)

    def _csrf(self):
        """获取/刷新 act_csrf_token（component_action 需要，缺失时为空也能用）"""
        self.csrf = self.s.cookies.get("act_csrf_token", "")
        return self.csrf

    # ---------- 鉴权校验 ----------
    def check_login(self):
        """校验 Cookie 是否有效（account.wps.cn 需 X-CSRFToken 头）"""
        r = self.s.post("https://account.wps.cn/p/auth/check",
                        headers={"X-CSRFToken": self.csrf}, json={}, timeout=15)
        d = r.json()
        if d.get("result") == "ok":
            nick = d.get("nickname", "") or "未设置"
            Log.ok(f"账号登录有效，用户：{nick}（uid={d.get('userid', self.user_id)}）")
            return True
        Log.fail(f"账号登录失效：{d.get('result', '')} {d.get('msg', '')}")
        return False

    # ---------- 签到 ----------
    def get_sign_stat(self):
        """获取签到状态"""
        r = self.s.get(f"{self.SIGN_BASE}/user_stat", params={"channel": ""}, timeout=20)
        d = r.json().get("data", {}) or {}
        Log.info(f"签到状态：今日已签={d.get('has_signed')} 本月连续={d.get('month_continuous_days')}天 "
                 f"累计={d.get('total_cumulative_days')}天")
        return d

    def _build_encrypt_payload(self):
        """获取公钥并构造加密参数 -> (token, extra)"""
        r = self.s.get(f"{self.SIGN_BASE}/encrypt/key", timeout=20)
        pem = base64.b64decode(r.json()["data"]).decode()
        aes_key = gen_aes_key()
        token = rsa_encrypt(aes_key, pem)
        payload = json.dumps({"user_id": self.user_id, "platform": 8})
        extra = aes_encrypt(payload, aes_key)
        return token, extra

    def sign_in(self):
        """执行每日签到"""
        Log.step("开始每日签到")
        stat = self.get_sign_stat()
        if stat.get("has_signed"):
            Log.ok("今日已签到，跳过")
            return True
        try:
            token, extra = self._build_encrypt_payload()
        except Exception as e:
            Log.fail(f"加密参数构造失败：{e}")
            return False
        body = {"encrypt": True, "extra": extra, "pay_origin": "ad_ucs_rwzx sign", "channel": ""}
        r = self.s.post(f"{self.SIGN_BASE}/sign_in",
                        headers={"token": token}, json=body, timeout=20)
        d = r.json()
        if d.get("result") == "ok":
            data = d.get("data", {}) or {}
            rewards = data.get("reward_list") or []
            rwd = "、".join([x.get("title", "") for x in rewards]) or "积分奖励"
            Log.ok(f"签到成功！获得：{rwd}")
            if data.get("medal"):
                Log.ok(f"获得勋章：{data['medal'].get('title', '')}")
            return True
        Log.fail(f"签到失败：{d.get('msg', r.text[:120])}")
        return False

    # ---------- 任务中心 ----------
    def get_tasks(self):
        """从 page_info 获取任务列表"""
        r = self.s.get(f"{self.ACT_BASE}/activity/page_info",
                       params={"activity_number": ACTIVITY_NUMBER, "page_number": PAGE_NUMBER,
                               "filter_params": json.dumps(FILTER_PARAMS)}, timeout=20)
        data = r.json().get("data", []) or []
        for c in data:
            tc = c.get("task_center") or {}
            if tc.get("task_list"):
                return tc["task_list"]
        return []

    def _comp_action(self, bus_info):
        """调用 component_action（任务中心组件动作）"""
        body = {
            "component_uniq_number": {
                "activity_number": ACTIVITY_NUMBER,
                "page_number": PAGE_NUMBER,
                "component_number": COMPONENT_NUMBER,
                "component_node_id": COMPONENT_NODE_ID,
                "filter_params": FILTER_PARAMS,
            },
            "component_type": COMPONENT_TYPE,
            **bus_info,
        }
        r = self.s.post(f"{self.ACT_BASE}/activity/component_action",
                        headers={"X-Act-Csrf-Token": self._csrf()}, json=body, timeout=20)
        d = r.json()
        tc = (d.get("data") or {}).get("task_center") or {}
        return d, tc

    def do_browse_task(self, task):
        """完成单个浏览类任务：start -> task_info -> 等待 -> task_finish -> reward"""
        tid = task["task_id"]
        title = task.get("title", "")
        # 1. start 获取 consumptionToken
        d, tc = self._comp_action({"component_action": "task_center.start",
                                   "task_center": {"task_id": tid}})
        token = tc.get("token", "")
        if not token:
            Log.fail(f"[{title}] start 失败：{d.get('msg', '')} {tc.get('reason', '')}")
            return False
        # 2. task_info 获取浏览时长
        batch_tag = int(time.time() * 1000)
        r = self.s.get(f"{self.ACT_BASE}/user/task_center/task_info",
                       params={"batch_tag": batch_tag, "token": token}, timeout=20)
        info = r.json().get("data", {}) or {}
        browse_second = info.get("browse_second", 10)
        start_at = info.get("start_at", 0)
        Log.info(f"[{title}] 开始浏览，需等待 {browse_second} 秒")
        # 3. 等待浏览时长
        time.sleep(browse_second + BROWSE_EXTRA_WAIT)
        # 4. task_finish
        r = self.s.post(f"{self.ACT_BASE}/user/task_center/task_finish",
                        headers={"X-Act-Csrf-Token": self._csrf()},
                        json={"batch_tag": batch_tag + start_at, "token": token}, timeout=20)
        state = (r.json().get("data") or {}).get("state")
        if state != 1:
            Log.fail(f"[{title}] task_finish 未完成 state={state}")
            return False
        # 5. reward 领取奖励
        self._sleep()
        d, tc = self._comp_action({"component_action": "task_center.reward",
                                   "task_center": {"task_id": tid}})
        if tc.get("success"):
            Log.ok(f"[{title}] 完成！奖励：{task.get('rewards', '已领取')}")
            return True
        Log.warn(f"[{title}] reward 返回 success={tc.get('success')} status={tc.get('status')}")
        return False

    def show_tasks(self, tasks):
        """展示所有任务状态"""
        # 任务状态：0=未完成 2=已完成 3=已领取
        status_map = {0: "未完成", 2: "已完成", 3: "已领取"}
        # 可自动完成的类型
        auto_types = {"browse"}
        Log.step("任务清单")
        print(f"{'ID':>4} {'状态':<6} {'类型':<16} {'可自动':<6} 标题")
        print("-" * 60)
        for t in tasks:
            st = status_map.get(t.get("task_status", 0), str(t.get("task_status")))
            ev = t.get("task_event", "")
            auto = "是" if ev in auto_types else "否"
            print(f"{t['task_id']:>4} {st:<6} {ev:<16} {auto:<6} {t.get('title','')}")

    def run_tasks(self):
        """执行任务"""
        Log.step("开始处理任务")
        tasks = self.get_tasks()
        if not tasks:
            Log.warn("未获取到任务列表")
            return
        self.show_tasks(tasks)

        if DO_BROWSE_TASKS:
            browse_tasks = [t for t in tasks if t.get("task_event") == "browse" and t.get("task_status") == 0]
            if browse_tasks:
                Log.info(f"发现 {len(browse_tasks)} 个可自动完成的浏览任务")
                for t in browse_tasks:
                    self.do_browse_task(t)
                    self._sleep()
            else:
                Log.info("没有待完成的浏览任务")

        # 提示无法自动完成的任务
        manual = [t for t in tasks if t.get("task_event") != "browse" and t.get("task_status") == 0]
        if manual:
            Log.warn(f"以下 {len(manual)} 个任务需手动完成（点击/分享/开通会员等无法纯接口完成）：")
            for t in manual:
                print(f"    - [{t.get('task_event')}] {t.get('title','')}  奖励:{t.get('rewards','')}")

    # ---------- 主流程 ----------
    def run(self):
        Log.step("WPS 自动签到 & 任务")
        if not self.check_login():
            return
        try:
            if DO_SIGN_IN:
                self.sign_in()
        except Exception as e:
            Log.fail(f"签到异常：{e}")
        try:
            self.run_tasks()
        except Exception as e:
            Log.fail(f"任务异常：{e}")
        # 最终状态
        Log.step("执行完毕，最终签到状态")
        try:
            self.get_sign_stat()
        except Exception:
            pass
        Log.ok("全部流程结束")


def parse_cookies(raw):
    """解析多账号 Cookie，用换行或 & 分隔"""
    if not raw:
        return []
    parts = re.split(r'[\n&]+', raw)
    return [p.strip() for p in parts if p.strip()]


if __name__ == "__main__":
    cookies = parse_cookies(COOKIE)
    if not cookies:
        Log.fail("未配置 Cookie，请设置环境变量 WPS_COOKIE 或编辑脚本 DEFAULT_COOKIE")
        sys.exit(1)
    Log.info(f"共 {len(cookies)} 个账号待执行")
    for idx, ck in enumerate(cookies, 1):
        if len(cookies) > 1:
            Log.step(f"账号 {idx}/{len(cookies)}")
        try:
            WpsAuto(ck).run()
        except Exception as e:
            Log.fail(f"账号 {idx} 执行异常：{e}")
        if idx < len(cookies):
            time.sleep(3)
