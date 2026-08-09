# -*- coding: utf-8 -*-
"""
config.py — Grok 独立注册机 配置。

所有密钥/凭据都从环境变量读取（默认空），不在仓库里留明文。
支持把变量写进同目录的 .env 文件（在 WebUI「配置」页保存，或参照 .env.example）；
.env 只在对应环境变量尚未设置时生效，不会覆盖真实的进程环境变量。
"""

import os


# ---------------------------------------------------------------- .env 加载
def _load_dotenv(path=None):
    """零依赖 .env 读取器：解析 KEY=VALUE，忽略空行与 # 注释。
    只在 os.environ 里尚未设置该 KEY 时填入（真实环境变量优先）。"""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


_load_dotenv()


def _env(name, default=""):
    return os.environ.get(name, default)


def _env_int(name, default):
    try:
        return int(_env(name, str(default)) or default)
    except (TypeError, ValueError):
        return int(default)


# ---------------------------------------------------------------- 代理出口
# 注册机出口代理：默认指向本地代理池 relay(10809)，或 Clash 混合端口(7897)。
# 每号独立 IP 由 register_grok_http.py 调代理池控制口(10810/next)分配。
CLASH_PROXY = _env("CLASH_PROXY", "http://127.0.0.1:10809")

# ---------------------------------------------------------------- 临时邮箱（Grok 注册取码）
# provider: remail | yyds | gptmail | moemail | cfmail | custom（默认 remail）
TEMP_EMAIL_PROVIDER = _env("TEMP_EMAIL_PROVIDER", "remail").strip().lower() or "remail"

# ReMail（remail.aishop6.com）——付费接码平台，X-Api-Key 认证，下单租用邮箱
REMAIL_BASE_URL = _env("REMAIL_BASE_URL", "https://remail.aishop6.com")
REMAIL_API_KEY = _env("REMAIL_API_KEY", "")       # rk-... 格式，remail 后台获取
REMAIL_PROJECT_ID = int(_env("REMAIL_PROJECT_ID", "3") or "3")   # Grok=3
REMAIL_PRODUCT_ID = int(_env("REMAIL_PRODUCT_ID", "8") or "8")   # Grok microsoft 邮箱

# YYDS Mail（vip.215.im / maliapi.215.im）
YYDS_BASE_URL = _env("YYDS_BASE_URL", "https://maliapi.215.im")
YYDS_API_KEY = _env("YYDS_API_KEY", "")  # AC-... 格式，profile 页获取

# GPTMail（mail.chatgpt.org.uk），支持公共测试 key "gpt-test"
GPTMAIL_BASE_URL = _env("GPTMAIL_BASE_URL", "https://mail.chatgpt.org.uk")
GPTMAIL_API_KEY = _env("GPTMAIL_API_KEY", "gpt-test")

# MoeMail（beilunyang/moemail，需自部署）
MOEMAIL_BASE_URL = _env("MOEMAIL_BASE_URL", "https://moemail.example.com")
MOEMAIL_API_KEY = _env("MOEMAIL_API_KEY", "")
MOEMAIL_DOMAIN = _env("MOEMAIL_DOMAIN", "")  # 留空则运行时从已有邮箱推断
MOEMAIL_EXPIRY_MS = int(_env("MOEMAIL_EXPIRY_MS", "3600000") or "3600000")  # 1h

# Cloudflare Temp Email（dreamhunter2333/cloudflare_temp_email，建议自部署 Workers）
CFMAIL_BASE_URL = _env("CFMAIL_BASE_URL", "https://temp-email-api.awsl.uk")
CFMAIL_ADMIN_PASSWORD = _env("CFMAIL_ADMIN_PASSWORD", "")  # x-admin-auth header
CFMAIL_SITE_PASSWORD = _env("CFMAIL_SITE_PASSWORD", "")   # x-custom-auth header（可选）

# 自定义临时邮箱（配置驱动，接任意 REST 风格 API）——TEMP_EMAIL_PROVIDER=custom 时启用
CUSTOM_MAIL_BASE_URL = _env("CUSTOM_MAIL_BASE_URL", "")
CUSTOM_MAIL_AUTH_HEADER = _env("CUSTOM_MAIL_AUTH_HEADER", "")
CUSTOM_MAIL_API_KEY = _env("CUSTOM_MAIL_API_KEY", "")
CUSTOM_MAIL_AUTH_PREFIX = _env("CUSTOM_MAIL_AUTH_PREFIX", "")
CUSTOM_MAIL_CREATE_METHOD = _env("CUSTOM_MAIL_CREATE_METHOD", "POST")
CUSTOM_MAIL_CREATE_PATH = _env("CUSTOM_MAIL_CREATE_PATH", "")
CUSTOM_MAIL_CREATE_BODY = _env("CUSTOM_MAIL_CREATE_BODY", "")
CUSTOM_MAIL_EMAIL_PATH = _env("CUSTOM_MAIL_EMAIL_PATH", "email")
CUSTOM_MAIL_ID_PATH = _env("CUSTOM_MAIL_ID_PATH", "")
CUSTOM_MAIL_TOKEN_PATH = _env("CUSTOM_MAIL_TOKEN_PATH", "")
CUSTOM_MAIL_FETCH_METHOD = _env("CUSTOM_MAIL_FETCH_METHOD", "GET")
CUSTOM_MAIL_FETCH_PATH = _env("CUSTOM_MAIL_FETCH_PATH", "")
CUSTOM_MAIL_FETCH_AUTH = _env("CUSTOM_MAIL_FETCH_AUTH", "key").strip().lower()
CUSTOM_MAIL_LIST_PATH = _env("CUSTOM_MAIL_LIST_PATH", "")
CUSTOM_MAIL_DETAIL_PATH = _env("CUSTOM_MAIL_DETAIL_PATH", "")
CUSTOM_MAIL_MSG_ID_PATH = _env("CUSTOM_MAIL_MSG_ID_PATH", "id")
CUSTOM_MAIL_MSG_PATH = _env("CUSTOM_MAIL_MSG_PATH", "")


# ---------------------------------------------------------------- 打码平台（解 Turnstile）
# CapSolver：https://dashboard.capsolver.com 注册获取，CAP- 开头
CAPSOLVER_API_KEY = _env("CAPSOLVER_API_KEY", "")
# EZ-Captcha：https://www.ez-captcha.com 注册获取
EZCAPTCHA_API_KEY = _env("EZCAPTCHA_API_KEY", "")
EZCAPTCHA_API_BASE = _env("EZCAPTCHA_API_BASE", "https://api.ez-captcha.com")
# YesCaptcha：https://yescaptcha.com 注册获取（API 与 CapSolver 兼容）
YESCAPTCHA_API_KEY = _env("YESCAPTCHA_API_KEY", "")
YESCAPTCHA_API_BASE = _env("YESCAPTCHA_API_BASE", "https://api.yescaptcha.com")


# ---------------------------------------------------------------- 标准 token 导出
# 注册成功后的 sso token 落盘目录（tokens/grok/<email>.sso.json）
TOKEN_OUTPUT_DIR = _env("TOKEN_OUTPUT_DIR", "tokens")


# ---------------------------------------------------------------- SUB2API（Grok OAuth 导入）
SUB2API_URL = _env("SUB2API_URL", "")
SUB2API_EMAIL = _env("SUB2API_EMAIL", "")
SUB2API_PASSWORD = _env("SUB2API_PASSWORD", "")
SUB2API_ADMIN_KEY = _env("SUB2API_ADMIN_KEY", "")  # x-api-key 直连认证，有则优先于账密
SUB2API_GROK_GROUP = _env("SUB2API_GROK_GROUP", "grok")  # platform=grok 的目标分组
SUB2API_GROK_PROXY_ID = int(_env("SUB2API_GROK_PROXY_ID", "0") or "0")  # 0=不指定


# ---------------------------------------------------------------- 打码重试参数（可选调优）
# ProxyLess 打码快速重试次数（默认 3），失败间隔 5s；可通过环境变量 GROK_CAP_RETRIES 覆盖
GROK_CAP_RETRIES = int(_env("GROK_CAP_RETRIES", "3") or "3")
