#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
青龙面板 Open API 封装
======================
用于机器人自动提交 WPS Cookie 到青龙环境变量，以及查询/管理环境变量。

青龙面板配置 Open API：
  1. 登录青龙面板
  2. 系统设置 -> 应用设置 -> 新建应用
  3. 名称任意（如 ql-wps-bot），权限勾选 环境变量
  4. 复制 client_id 和 client_secret

接口文档：https://qinglong.ukit.top/
"""

import requests
import json
import time


class QingLongAPI:
    def __init__(self, base_url, client_id, client_secret):
        """
        :param base_url: 青龙面板地址，如 http://127.0.0.1:5700
        :param client_id: 应用 client_id
        :param client_secret: 应用 client_secret
        """
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expire = 0
        self.s = requests.Session()
        self.s.headers.update({"Content-Type": "application/json"})

    def _auth(self):
        """获取青龙 token（带缓存，提前60秒刷新）"""
        now = time.time()
        if self.token and self.token_expire > now + 60:
            return True
        url = f"{self.base_url}/open/auth/token"
        params = {"client_id": self.client_id, "client_secret": self.client_secret}
        try:
            r = self.s.get(url, params=params, timeout=15)
            d = r.json()
            if d.get("code") == 200:
                data = d.get("data", {})
                self.token = data.get("token")
                self.token_expire = data.get("expiration", 0) / 1000 or now + 3600
                self.s.headers["Authorization"] = f"Bearer {self.token}"
                return True
            raise RuntimeError(f"青龙认证失败：{d.get('message', d)}")
        except Exception as e:
            raise RuntimeError(f"青龙认证异常：{e}")

    def _request(self, method, path, **kwargs):
        self._auth()
        url = f"{self.base_url}/open{path}"
        r = self.s.request(method, url, timeout=20, **kwargs)
        d = r.json()
        if d.get("code") != 200:
            raise RuntimeError(f"青龙API错误：{d.get('message', d)}")
        return d.get("data", {})

    def get_envs(self, search_value=""):
        """获取环境变量列表"""
        params = {"searchValue": search_value} if search_value else {}
        return self._request("GET", "/envs", params=params)

    def create_env(self, name, value, remarks=""):
        """创建环境变量"""
        body = [{"name": name, "value": value, "remarks": remarks}]
        return self._request("POST", "/envs", json=body)

    def update_env(self, env_id, name, value, remarks=""):
        """更新环境变量"""
        body = [{"id": env_id, "name": name, "value": value, "remarks": remarks}]
        return self._request("PUT", "/envs", json=body)

    def upsert_env(self, name, value, remarks=""):
        """
        创建或更新环境变量
        如果存在则更新，不存在则创建
        """
        envs = self.get_envs(search_value=name)
        target = None
        for env in envs:
            if env.get("name") == name:
                target = env
                break
        if target:
            return self.update_env(target["id"], name, value, remarks)
        return self.create_env(name, value, remarks)

    def delete_env(self, env_id):
        """删除环境变量"""
        return self._request("DELETE", "/envs", json=[env_id])

    def get_crons(self, search_value=""):
        """获取定时任务列表"""
        params = {"searchValue": search_value} if search_value else {}
        return self._request("GET", "/crons", params=params)

    def run_cron(self, cron_id):
        """执行指定定时任务"""
        return self._request("PUT", "/crons/run", json=[cron_id])
