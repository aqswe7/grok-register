# -*- coding: utf-8 -*-
"""
webui/scripts.py — Grok 独立注册机 WebUI 的脚本与配置 schema。

- SCRIPTS：面板「Grok 注册」表单（运行参数）
- ENV_SCHEMA：「配置」页的环境变量分组（临时邮箱/打码平台/代理池/SUB2API 等）
"""

# ============================================================ 运行脚本
SCRIPTS = [
    {
        "id": "register_grok",
        "file": "register_grok_http.py",
        "category": "Grok 注册",
        "title": "Grok 注册（HTTP 协议版）",
        "desc": "Grok (x.ai) 纯 HTTP 协议批量注册：临时邮箱收码 → Turnstile 打码 → 建号 → 取 sso。"
                "支持注册后自动导入 SUB2API Grok 分组。需：可用出口代理(过 Cloudflare) + 临时邮箱 key"
                " + 打码平台 key(至少一个)。",
        "args": [
            {"flag": "--count", "type": "int", "default": 1, "help": "注册总数"},
            {"flag": "--concurrency", "type": "int", "default": 1,
             "help": "并发数(每号自动分配独立代理 IP)。注意 remail 平台并发上限约 10，建议 4-8"},
            {"flag": "--provider", "type": "choice",
             "choices": ["", "remail", "yyds", "gptmail", "moemail", "cfmail", "custom"], "default": "",
             "help": "临时邮箱来源(留空=用 .env 的 TEMP_EMAIL_PROVIDER；在「配置」页填好对应 key)"},
            {"flag": "--sub2api", "type": "bool", "default": False,
             "help": "注册成功后导入 SUB2API，目标分组见 SUB2API_GROK_GROUP"},
            {"flag": "--sub2api-group", "type": "str", "default": "",
             "help": "SUB2API Grok 分组名(留空取 SUB2API_GROK_GROUP)"},
            {"flag": "--node", "type": "str", "default": "auto",
             "help": "Clash 出口节点(过 grok CF，如 '美国 01'；留 auto 自动探测；不开 Clash 直接走代理池)"},
            {"flag": "--mailbox-attempts", "type": "int", "default": 6,
             "help": "发码域名被拒时单号自动更换邮箱次数"},
            {"flag": "--code-timeout", "type": "int", "default": 75,
             "help": "单个临时邮箱等待验证码秒数"},
            {"flag": "--rotate-every", "type": "int", "default": 5,
             "help": "批量每 N 个账号重新探测出口节点(0=不轮换，仅 auto 模式)"},
        ],
    },
]


# ============================================================ 配置页 schema
ENV_SCHEMA = [
    {
        "group": "临时邮箱（Grok 收验证码）",
        "tests": [{"target": "temp_email", "label": "测试建号"}],
        "items": [
            {"key": "TEMP_EMAIL_PROVIDER", "type": "choice",
             "choices": ["remail", "yyds", "gptmail", "moemail", "cfmail", "custom"], "default": "remail",
             "help": "默认临时邮箱 provider。也可以在「Grok 注册」表单里临时指定。"},
            {"key": "REMAIL_API_KEY", "secret": True, "required": True,
             "help": "ReMail API key(rk- 开头)，https://remail.aishop6.com 后台获取。Grok 主推。"},
            {"key": "REMAIL_PROJECT_ID", "type": "int", "default": "3",
             "help": "ReMail 项目 ID：Grok=3；不同账号/服务可能不同，以你后台为准。"},
            {"key": "REMAIL_PRODUCT_ID", "type": "int", "default": "8",
             "help": "ReMail 产品 ID：Grok microsoft 邮箱=8；按你后台的库存产品设置。"},
            {"key": "YYDS_API_KEY", "secret": True,
             "help": "YYDS Mail key(AC- 开头)，profile 页获取(备选 provider)"},
            {"key": "YYDS_BASE_URL", "default": "https://maliapi.215.im",
             "help": "YYDS Mail API 根地址"},
            {"key": "GPTMAIL_API_KEY", "secret": True, "default": "gpt-test",
             "help": "GPTMail key(mail.chatgpt.org.uk)，公共测试 key=gpt-test"},
            {"key": "MOEMAIL_API_KEY", "secret": True, "help": "MoeMail key(自部署，备选)"},
            {"key": "MOEMAIL_BASE_URL", "help": "MoeMail 自部署地址"},
            {"key": "CFMAIL_ADMIN_PASSWORD", "secret": True,
             "help": "Cloudflare Temp Email admin 密码(自部署，备选)"},
            {"key": "CFMAIL_BASE_URL", "help": "Cloudflare Temp Email 地址"},
        ],
    },
    {
        "group": "打码平台（解 Turnstile，至少配一个）",
        "items": [
            {"key": "CAPSOLVER_API_KEY", "secret": True, "required": True,
             "help": "CapSolver key(CAP- 开头)。https://dashboard.capsolver.com 注册充值后获取。主推。"},
            {"key": "EZCAPTCHA_API_KEY", "secret": True,
             "help": "EZ-Captcha key(备选打码平台)，https://www.ez-captcha.com"},
            {"key": "YESCAPTCHA_API_KEY", "secret": True,
             "help": "YesCaptcha key(备选打码平台)，https://yescaptcha.com"},
        ],
    },
    {
        "group": "代理出口（必须可用）",
        "tests": [{"target": "proxy", "label": "测试代理"}],
        "items": [
            {"key": "CLASH_PROXY", "default": "http://127.0.0.1:10809",
             "help": "出口代理地址。默认本地代理池 relay(10809)；不用代理池时填 Clash 混合端口如"
                     " http://127.0.0.1:7897（同时把 PROXY_CTRL 留空）。"},
            {"key": "PROXY_CTRL", "default": "http://127.0.0.1:10810",
             "help": "代理池控制口地址(用于 /next 给每号分配独立 IP)。留空=不用代理池，所有号共用"
                     " CLASH_PROXY 单出口。"},
            {"key": "PROXY_POOL_LIST", "type": "textarea",
             "help": "代理池 IP 列表：每行一个 user:pass@host:port。填写并保存后，relay 会自动改用它"
                     "（写入本目录 proxies.txt）；留空=用默认文件 miyaip_pool.txt（若有）。"},
            {"key": "RELAY_PORT", "type": "int", "default": "10809",
             "help": "内置代理池出口端口（与 CLASH_PROXY 端口一致）。仅当使用内置 relay 时生效。"},
            {"key": "RELAY_CTRL_PORT", "type": "int", "default": "10810",
             "help": "内置代理池控制口端口（与 PROXY_CTRL 端口一致）。仅当使用内置 relay 时生效。"},
        ],
    },
    {
        "group": "SUB2API（可选，注册后导入 Grok）",
        "items": [
            {"key": "SUB2API_URL", "help": "SUB2API 管理接口地址，如 https://api-hub.asia"},
            {"key": "SUB2API_EMAIL", "help": "SUB2API 登录邮箱(与下面密码二选一，或用 admin key)"},
            {"key": "SUB2API_PASSWORD", "secret": True, "help": "SUB2API 登录密码"},
            {"key": "SUB2API_ADMIN_KEY", "secret": True,
             "help": "SUB2API 管理 key(x-api-key 直连认证)，有则优先于账密"},
            {"key": "SUB2API_GROK_GROUP", "default": "grok",
             "help": "Grok 目标分组名(platform=grok，需后台先建好)"},
            {"key": "SUB2API_GROK_PROXY_ID", "type": "int", "default": "0",
             "help": "可选：SUB2API 后台代理 ID，0=不指定"},
        ],
    },
    {
        "group": "高级调优（可选）",
        "items": [
            {"key": "GROK_CAP_RETRIES", "type": "int", "default": "3",
             "help": "打码 ProxyLess 快速重试次数(间隔 5s)。CapSolver 节点被 Cloudflare 标记时提高此值可提升成功率，"
                     "如 5-8；也会相应增加打码消耗。"},
        ],
    },
]


def script_by_id(sid):
    for s in SCRIPTS:
        if s["id"] == sid:
            return s
    return None


def env_keys():
    keys = []
    for g in ENV_SCHEMA:
        for it in g["items"]:
            keys.append(it["key"])
    return keys


EXTERNAL_LINKS = [
    {"title": "ReMail 控制台", "url": "https://remail.aishop6.com", "desc": "临时邮箱余额/订单管理"},
    {"title": "CapSolver 控制台", "url": "https://dashboard.capsolver.com", "desc": "打码余额/用量"},
    {"title": "MiyaIP 动态代理", "url": "https://miyaip.com", "desc": "动态住宅代理购买/生成 IP 池"},
]
EMBED_PAGES = []
