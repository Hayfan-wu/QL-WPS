#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WPS 会员中心 自动签到 & 任务完成脚本
=====================================
功能：
  1. 每日签到（RSA + AES 加密，已验证可用）
  2. 自适应任务完成引擎 — 按任务类型自动选择完成策略，不硬编码任务ID
     - click / share / scan  → task_center.finish + reward（直接完成）
     - browse                → start → task_info → 等待 → task_finish → reward
     - exchange_traffic      → start → 访问jump_url+token → finish → reward
     - toReceive(待领奖)      → 直接 reward
     - 其余类型(trade/auth/invite/subscribe等) → 跳过并提示
  3. 任务变更后仍能自适应处理（按 task_event + task_status 分发）

依赖：
  pip install requests pycryptodome

用法：
  方式一（环境变量，推荐，适配青龙面板）：
    export WPS_COOKIE="账号1的Cookie"
    多账号用换行或 & 分隔：
    export WPS_COOKIE="账号1cookie
账号2cookie"
  方式二（直接编辑脚本）：将下方 DEFAULT_COOKIE 改为你自己的 Cookie
  然后运行：python3 wps_auto.py

获取 Cookie 方法：
  浏览器登录 WPS 个人中心（account.wps.cn），F12 -> Network ->
  随便找一个请求，复制 Request Headers 中的 Cookie 值。
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
# 优先从环境变量 WPS_COOKIE 读取（适配青龙面板，多账号用换行或 & 分隔）
DEFAULT_COOKIE = ""
COOKIE = os.getenv("WPS_COOKIE", DEFAULT_COOKIE)

# 活动地址（一般无需修改）
ACTIVITY_NUMBER = "HD2025031821201822"
PAGE_NUMBER = "YM2025040908558269"
# 任务中心组件标识（来自 page_info，一般无需修改）
COMPONENT_NUMBER = "ZJ2025040709458367"
COMPONENT_NODE_ID = "FN1744160180RthG"
COMPONENT_TYPE = 35
FILTER_PARAMS = {"position": "ad_rwzx_invite_test", "token": "61b3f3ab86984a191927bfe7748b85a5"}

# 浏览任务等待冗余秒数
BROWSE_EXTRA_WAIT = 3
# 请求间隔（秒）
REQUEST_INTERVAL = 1.5
# finish 后等待秒数（前端默认3秒后刷新状态）
FINISH_DELAY = 3
# 是否执行签到
DO_SIGN_IN = True
# ======================== 配置区结束 ========================

# 任务状态枚举
TASK_UNDONE = 0       # 未完成
TASK_TO_RECEIVE = 1   # 待领奖
TASK_DONE = 2         # 已完成

# 可直接 finish 完成的任务类型
FINISH_TYPES = {"click", "share", "scan"}
# 浏览类任务
BROWSE_TYPES = {"browse"}
# 三方换量任务
TRAFFIC_TYPES = {"exchange_traffic"}
# 无法自动完成的任务类型
MANUAL_TYPES = {"trade", "auth", "invite", "subscribe", "improve",
                "promotional", "accrue", "visit_current", "reservation",
                "desktop_install", "desktop_visit"}


# ----------------------- 日志 -----------------------
class Log:
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
    rnd = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(22))
    ts = str(int(time.time()))
    return rnd + ts


def rsa_encrypt(plain, pem):
    key = RSA.import_key(pem)
    cipher = PKCS1_v1_5.new(key)
    return base64.b64encode(cipher.encrypt(plain.encode())).decode()


def aes_encrypt(payload_str, aes_key):
    key = aes_key.encode()
    iv = aes_key[:16].encode()
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
        for item in cookie.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                self.s.cookies.set(k, v, domain=".wps.cn")
        self.user_id = self._extract_uid(cookie)
        self.csrf = self.s.cookies.get("csrf", "")
        self.stats = {"ok": 0, "skip": 0, "fail": 0}

    @staticmethod
    def _extract_uid(cookie):
        m = re.search(r'uid=(\d+)', cookie)
        return int(m.group(1)) if m else 0

    def _sleep(self, t=None):
        time.sleep(t if t else REQUEST_INTERVAL)

    def _act_csrf(self):
        return self.s.cookies.get("act_csrf_token", "")

    # ---------- 鉴权 ----------
    def check_login(self):
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
        r = self.s.get(f"{self.SIGN_BASE}/user_stat", params={"channel": ""}, timeout=20)
        d = r.json().get("data", {}) or {}
        Log.info(f"签到状态：今日已签={d.get('has_signed')} 本月连续={d.get('month_continuous_days')}天 "
                 f"累计={d.get('total_cumulative_days')}天")
        return d

    def _build_encrypt_payload(self):
        r = self.s.get(f"{self.SIGN_BASE}/encrypt/key", timeout=20)
        pem = base64.b64decode(r.json()["data"]).decode()
        aes_key = gen_aes_key()
        token = rsa_encrypt(aes_key, pem)
        payload = json.dumps({"user_id": self.user_id, "platform": 8})
        extra = aes_encrypt(payload, aes_key)
        return token, extra

    def sign_in(self):
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
        r = self.s.post(f"{self.SIGN_BASE}/sign_in", headers={"token": token}, json=body, timeout=20)
        d = r.json()
        if d.get("result") == "ok":
            data = d.get("data", {}) or {}
            rewards = data.get("reward_list") or []
            rwd = "、".join([x.get("title", "") for x in rewards]) or "积分奖励"
            Log.ok(f"签到成功！获得：{rwd}")
            return True
        Log.fail(f"签到失败：{d.get('msg', r.text[:120])}")
        return False

    # ---------- 任务中心 ----------
    def get_tasks(self):
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
                        headers={"X-Act-Csrf-Token": self._act_csrf()}, json=body, timeout=20)
        d = r.json()
        tc = (d.get("data") or {}).get("task_center") or {}
        return d, tc

    def _do_reward(self, task_id, title=""):
        d, tc = self._comp_action({"component_action": "task_center.reward",
                                   "task_center": {"task_id": task_id}})
        if tc.get("success"):
            Log.ok(f"[{title}] 奖励领取成功")
            self.stats["ok"] += 1
            return True
        Log.warn(f"[{title}] 领奖 success={tc.get('success')} status={tc.get('status')}")
        self.stats["fail"] += 1
        return False

    def _do_finish_and_reward(self, task):
        """click/share/scan 类任务：finish → reward"""
        tid = task["task_id"]
        title = task.get("title", "")
        d, tc = self._comp_action({"component_action": "task_center.finish",
                                   "task_center": {"task_id": tid}})
        if not tc.get("success"):
            Log.fail(f"[{title}] finish 失败 status={tc.get('status')} reason={tc.get('reason','')}")
            self.stats["fail"] += 1
            return False
        Log.info(f"[{title}] finish 成功，等待 {FINISH_DELAY}s 后领奖")
        time.sleep(FINISH_DELAY)
        return self._do_reward(tid, title)

    def _do_browse_task(self, task):
        """browse 类任务：start → task_info → 等待 → task_finish → reward"""
        tid = task["task_id"]
        title = task.get("title", "")
        d, tc = self._comp_action({"component_action": "task_center.start",
                                   "task_center": {"task_id": tid}})
        token = tc.get("token", "")
        if not token:
            Log.fail(f"[{title}] start 失败：{d.get('msg', '')} {tc.get('reason', '')}")
            self.stats["fail"] += 1
            return False
        batch_tag = int(time.time() * 1000)
        r = self.s.get(f"{self.ACT_BASE}/user/task_center/task_info",
                       params={"batch_tag": batch_tag, "token": token}, timeout=20)
        info = r.json().get("data", {}) or {}
        browse_second = info.get("browse_second", 10)
        start_at = info.get("start_at", 0)
        Log.info(f"[{title}] 浏览中，需等待 {browse_second} 秒")
        time.sleep(browse_second + BROWSE_EXTRA_WAIT)
        r = self.s.post(f"{self.ACT_BASE}/user/task_center/task_finish",
                        headers={"X-Act-Csrf-Token": self._act_csrf()},
                        json={"batch_tag": batch_tag + start_at, "token": token}, timeout=20)
        state = (r.json().get("data") or {}).get("state")
        if state != 1:
            Log.fail(f"[{title}] task_finish 未完成 state={state}")
            self.stats["fail"] += 1
            return False
        self._sleep()
        return self._do_reward(tid, title)

    def _do_traffic_task(self, task):
        """exchange_traffic 类任务：start → 访问jump_url+token → finish → reward"""
        tid = task["task_id"]
        title = task.get("title", "")
        d, tc = self._comp_action({"component_action": "task_center.start",
                                   "task_center": {"task_id": tid}})
        token = tc.get("token", "")
        jump_url = task.get("jump_url", "")
        if token and jump_url:
            full_url = f"{jump_url}{token}"
            Log.info(f"[{title}] 访问换量页面: {jump_url[:60]}...")
            try:
                self.s.get(full_url, timeout=15, allow_redirects=True)
            except Exception:
                pass
            time.sleep(2)
        self._sleep()
        d, tc = self._comp_action({"component_action": "task_center.finish",
                                   "task_center": {"task_id": tid}})
        if tc.get("success"):
            Log.info(f"[{title}] finish 成功，等待领奖")
            time.sleep(FINISH_DELAY)
            return self._do_reward(tid, title)
        Log.warn(f"[{title}] finish 未成功 status={tc.get('status')}（可能需在目标App内操作）")
        self.stats["fail"] += 1
        return False

    def _dispatch_task(self, task):
        """自适应任务分发：按 task_event + task_status 选择策略"""
        tid = task["task_id"]
        title = task.get("title", "")
        event = task.get("task_event", "")
        status = task.get("task_status", 0)

        # 已完成
        if status == TASK_DONE:
            self.stats["skip"] += 1
            return
        # 待领奖 → 直接领
        if status == TASK_TO_RECEIVE:
            Log.info(f"[{title}] 待领奖，直接领取")
            self._do_reward(tid, title)
            self._sleep()
            return
        # 未完成 → 按类型分发
        if event in FINISH_TYPES:
            Log.info(f"[{title}] click/share类，直接finish")
            self._do_finish_and_reward(task)
            self._sleep()
        elif event in BROWSE_TYPES:
            self._do_browse_task(task)
            self._sleep()
        elif event in TRAFFIC_TYPES:
            self._do_traffic_task(task)
            self._sleep()
        elif event in MANUAL_TYPES:
            Log.warn(f"[{title}] 类型={event}，需手动完成（{task.get('rewards', '')}）")
            self.stats["skip"] += 1
        else:
            # 未知类型，尝试通用 finish
            Log.info(f"[{title}] 未知类型={event}，尝试finish")
            self._do_finish_and_reward(task)
            self._sleep()

    def show_tasks(self, tasks):
        status_map = {0: "未完成", 1: "待领奖", 2: "已完成", 3: "无库存", 4: "过期", 7: "未完成"}
        Log.step("任务清单")
        print(f"{'ID':>4} {'状态':<6} {'类型':<16} 标题")
        print("-" * 60)
        for t in tasks:
            st = status_map.get(t.get("task_status", 0), str(t.get("task_status")))
            print(f"{t['task_id']:>4} {st:<6} {t.get('task_event',''):<16} {t.get('title','')}")

    def run_tasks(self):
        Log.step("开始处理任务")
        tasks = self.get_tasks()
        if not tasks:
            Log.warn("未获取到任务列表")
            return
        self.show_tasks(tasks)
        undone = [t for t in tasks if t["task_status"] in (TASK_UNDONE, TASK_TO_RECEIVE)]
        Log.info(f"待处理任务 {len(undone)} 个（共 {len(tasks)} 个）")
        for t in undone:
            self._dispatch_task(t)
        # 汇总
        Log.step(f"任务完成汇总：成功 {self.stats['ok']} / 跳过 {self.stats['skip']} / 失败 {self.stats['fail']}")

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
        try:
            Log.step("执行完毕，最终签到状态")
            self.get_sign_stat()
        except Exception:
            pass
        Log.ok("全部流程结束")


def parse_cookies(raw):
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
