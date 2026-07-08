#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram 机器人 - WPS & 青龙管理助手
=====================================
按流程图设计：
  1. 在群里 @机器人 wps登录，或私聊发送 /wps_login
  2. 机器人提示输入 Cookie
  3. 用户直接粘贴 Cookie（会话内无需重复 @/命令）
  4. 自动验证 WPS 登录 → 获取账号名
  5. 自动提交到青龙环境变量 WPS_COOKIE
  6. 反馈登录结果（成功/失败）
  7. 45 秒无响应自动退出会话

支持命令：
  /start       欢迎与帮助
  /help        查看帮助
  /wps_login   提交/更新 WPS Cookie
  /wps_query   查询 WPS 账号状态、签到、任务、抽奖次数
  /wps_manage  管理青龙环境变量（查看/删除）
  /wps_exec    立即执行一次 wps_auto.py 签到任务
  /cancel      取消当前会话

环境变量配置：
  BOT_TOKEN            Telegram Bot Token（从 @BotFather 获取）
  ALLOWED_USER_IDS     允许使用的用户 ID，多个用逗号分隔（可选，留空则允许所有人）
  QL_URL               青龙面板地址，如 http://127.0.0.1:5700
  QL_CLIENT_ID         青龙应用 client_id
  QL_CLIENT_SECRET     青龙应用 client_secret

群聊说明：
  第一次需要 @机器人 唤醒（如 @xxxbot wps登录），进入会话后 45 秒内直接发消息即可，
  无需重复 @。如机器人在群里不响应无 @ 的消息，请至 @BotFather 关闭该机器人的
  Privacy Mode（/setprivacy → Disable）。
"""

import os
import sys
import logging
import subprocess
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from wps_query import WpsQuery
from qinglong_api import QingLongAPI

# 配置
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ALLOWED_USER_IDS = os.getenv("ALLOWED_USER_IDS", "").strip()
QL_URL = os.getenv("QL_URL", "").strip()
QL_CLIENT_ID = os.getenv("QL_CLIENT_ID", "").strip()
QL_CLIENT_SECRET = os.getenv("QL_CLIENT_SECRET", "").strip()

# 会话超时时间（秒）
CONV_TIMEOUT = 45

# 状态定义
WAITING_COOKIE = 1

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _allowed(user_id: int) -> bool:
    """检查用户是否有权限"""
    if not ALLOWED_USER_IDS:
        return True
    allowed = [int(x.strip()) for x in ALLOWED_USER_IDS.split(",") if x.strip()]
    return user_id in allowed


def _ql_client():
    """创建青龙 API 客户端"""
    if not all([QL_URL, QL_CLIENT_ID, QL_CLIENT_SECRET]):
        raise RuntimeError("青龙面板未配置，请设置 QL_URL、QL_CLIENT_ID、QL_CLIENT_SECRET")
    return QingLongAPI(QL_URL, QL_CLIENT_ID, QL_CLIENT_SECRET)


def _is_mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """判断消息中是否 @ 了当前机器人（群聊场景）"""
    if not update.message:
        return False
    me = context.bot.username
    if update.message.text and f"@{me}" in update.message.text:
        return True
    if update.message.entities:
        for ent in update.message.entities:
            if ent.type == "mention":
                mention = update.message.text[ent.offset: ent.offset + ent.length]
                if mention.lower() == f"@{me}".lower():
                    return True
    return False


def _strip_mention(text: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    """去掉消息里的 @机器人 前缀"""
    me = context.bot.username
    return text.replace(f"@{me}", "").strip()


async def _reply_unauthorized(update: Update):
    await update.message.reply_text("⛔ 你没有权限使用此机器人。")


# ============= 命令处理器 =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    user = update.effective_user
    if not _allowed(user.id):
        await _reply_unauthorized(update)
        return

    text = (
        f"👋 你好，{user.first_name or '朋友'}！\n\n"
        "我是 WPS & 青龙管理助手，帮你快速提交 Cookie、查询状态、执行任务。\n\n"
        "常用命令：\n"
        "  /wps_login  - 提交 WPS Cookie 到青龙环境变量\n"
        "  /wps_query  - 查询 WPS 账号状态、任务、抽奖\n"
        "  /wps_manage - 管理青龙环境变量\n"
        "  /wps_exec   - 立即执行一次签到任务\n"
        "  /cancel     - 取消当前会话\n\n"
        "💡 提示：发送 /wps_login 后，直接在 45 秒内粘贴 Cookie 即可，无需重复命令。"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    user = update.effective_user
    if not _allowed(user.id):
        await _reply_unauthorized(update)
        return

    text = (
        "📖 使用帮助\n\n"
        "1️⃣ 登录 WPS 并提交 Cookie\n"
        "   /wps_login\n"
        "   然后粘贴你的 WPS Cookie（支持多账号，换行或 & 分隔）\n\n"
        "2️⃣ 查询账号状态\n"
        "   /wps_query\n\n"
        "3️⃣ 管理青龙环境变量\n"
        "   /wps_manage\n\n"
        "4️⃣ 立即执行签到任务\n"
        "   /wps_exec\n\n"
        "⏰ 登录会话 45 秒无响应会自动取消。"
    )
    await update.message.reply_text(text)


async def wps_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """启动登录流程"""
    user = update.effective_user
    if not _allowed(user.id):
        await _reply_unauthorized(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "🍪 请输入你的 WPS Cookie（支持多账号，用换行或 & 分隔）：\n\n"
        "提示：45 秒内未输入将自动取消。输入 /cancel 可随时退出。"
    )
    return WAITING_COOKIE


async def receive_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收用户输入的 Cookie"""
    cookie = update.message.text.strip()

    if not cookie or cookie.startswith("/"):
        await update.message.reply_text("⚠️ 请输入有效的 Cookie，不是命令。")
        return WAITING_COOKIE

    # 验证 WPS 登录并获取账号名
    await update.message.reply_text("🔍 正在验证 WPS Cookie 并获取账号信息，请稍候...")
    query = WpsQuery(cookie)
    ok, nickname, uid = query.check_login()
    if not ok:
        await update.message.reply_text(
            f"❌ WPS 登录验证失败：{nickname}\n"
            "请检查 Cookie 是否完整，尤其是 wps_sid、kso_sid、csrf、uid 等字段。"
        )
        return ConversationHandler.END

    # 提交到青龙环境变量
    await update.message.reply_text(
        f"✅ WPS 验证成功：{nickname}（uid={uid}）\n🚀 正在提交到青龙环境变量 WPS_COOKIE..."
    )
    try:
        ql = _ql_client()
        ql.upsert_env("WPS_COOKIE", cookie, remarks=f"{nickname}({uid})")
        await update.message.reply_text(
            f"🎉 登录成功并已提交到青龙！\n"
            f"👤 账号：{nickname}\n"
            f"🆔 uid：{uid}\n"
            f"📦 环境变量：WPS_COOKIE\n"
            f"⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "你可以使用 /wps_query 查询状态，/wps_exec 立即执行任务。"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ 提交到青龙失败：{e}\n"
            "但 WPS Cookie 验证是成功的，请检查青龙面板配置（QL_URL、QL_CLIENT_ID、QL_CLIENT_SECRET）。"
        )

    return ConversationHandler.END


async def wps_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询 WPS 状态"""
    user = update.effective_user
    if not _allowed(user.id):
        await _reply_unauthorized(update)
        return

    await update.message.reply_text("🔍 正在查询 WPS 账号状态，请稍候...")
    try:
        # 从青龙环境变量读取 Cookie
        ql = _ql_client()
        envs = ql.get_envs(search_value="WPS_COOKIE")
        cookie = ""
        for env in envs:
            if env.get("name") == "WPS_COOKIE":
                cookie = env.get("value", "")
                break
        if not cookie:
            await update.message.reply_text(
                "⚠️ 未在青龙环境变量中找到 WPS_COOKIE，请先执行 /wps_login 提交 Cookie。"
            )
            return

        report = WpsQuery(cookie).format_report()
        # Telegram 单条消息限制 4096 字符
        if len(report) > 4000:
            report = report[:4000] + "\n\n... 内容过长，已截断"
        await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(f"❌ 查询失败：{e}")


async def wps_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """管理青龙环境变量"""
    user = update.effective_user
    if not _allowed(user.id):
        await _reply_unauthorized(update)
        return

    await update.message.reply_text("🔍 正在查询青龙环境变量...")
    try:
        ql = _ql_client()
        envs = ql.get_envs(search_value="WPS_COOKIE")
        lines = ["📦 青龙环境变量（WPS_COOKIE）："]
        for env in envs:
            name = env.get("name", "")
            if name == "WPS_COOKIE":
                remark = env.get("remarks", "")
                value = env.get("value", "")
                preview = value[:30] + "..." if len(value) > 30 else value
                lines.append(f"\n🆔 {env['id']}\n备注：{remark}\n预览：{preview}")
        if len(lines) == 1:
            lines.append("\n暂无 WPS_COOKIE 环境变量")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"❌ 查询失败：{e}")


async def wps_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """立即执行签到任务"""
    user = update.effective_user
    if not _allowed(user.id):
        await _reply_unauthorized(update)
        return

    await update.message.reply_text("🚀 正在执行 WPS 签到任务，请稍候...")
    try:
        result = subprocess.run(
            [sys.executable, "wps_auto.py"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        output = result.stdout + result.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n\n... 输出过长，已截断"
        await update.message.reply_text(
            f"✅ 执行完成（返回码 {result.returncode}）：\n```\n{output}\n```",
            parse_mode="Markdown",
        )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ 执行超时（超过 5 分钟）。")
    except Exception as e:
        await update.message.reply_text(f"❌ 执行失败：{e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消当前会话"""
    await update.message.reply_text("✋ 已取消当前操作。")
    return ConversationHandler.END


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """未知命令"""
    await update.message.reply_text("⚠️ 未知命令，请输入 /start 或 /help 查看帮助。")


async def mention_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """群聊中 @机器人 + 关键词 的入口"""
    user = update.effective_user
    if not _allowed(user.id):
        await _reply_unauthorized(update)
        return

    text = _strip_mention(update.message.text or "", context).lower()
    if "登录" in text or "login" in text or text.endswith("wps登录") or text == "wps登录":
        return await wps_login(update, context)
    if "查询" in text or text.endswith("wps查询") or text == "wps查询":
        return await wps_query(update, context)
    if "管理" in text or text.endswith("wps管理") or text == "wps管理":
        return await wps_manage(update, context)
    if "执行" in text or text.endswith("wps执行") or text == "wps执行":
        return await wps_exec(update, context)

    # 默认响应
    await update.message.reply_text(
        "👋 收到！请输入 /start 查看帮助，或直接发送 /wps_login 开始登录。"
    )


# ============= 主入口 =============

def main():
    if not BOT_TOKEN:
        print("错误：未设置 BOT_TOKEN 环境变量")
        sys.exit(1)

    application = Application.builder().token(BOT_TOKEN).build()

    # 登录会话处理器（45秒超时）
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("wps_login", wps_login)],
        states={
            WAITING_COOKIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cookie)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=CONV_TIMEOUT,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(login_conv)
    application.add_handler(CommandHandler("wps_query", wps_query))
    application.add_handler(CommandHandler("wps_manage", wps_manage))
    application.add_handler(CommandHandler("wps_exec", wps_exec))
    application.add_handler(CommandHandler("cancel", cancel))

    # 群聊 @机器人 入口（需在 @BotFather 关闭 Privacy Mode 才能生效）
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Entity("mention") & filters.ChatType.GROUPS, mention_entry)
    )

    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("🤖 WPS Bot 已启动，按 Ctrl+C 停止")
    application.run_polling()


if __name__ == "__main__":
    main()
