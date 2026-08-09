# -*- coding: utf-8 -*-
"""
webui/server.py — Grok 独立注册机 Web 面板后端(FastAPI)。

只绑 127.0.0.1（含 .env 密钥编辑，绝不监听公网）。职责：
  - 提供脚本 schema / .env 配置 给前端渲染表单
  - 把表单提交拼成命令行，subprocess 后台跑，SSE 实时推 stdout
  - 连通测试：临时邮箱建号 / 代理出口

启动：  python -m uvicorn webui.server:app --port 8799   (或双击 start.bat)
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# 启动前由系统显式提供的变量始终优先于 WebUI 保存的 .env。
BOOT_ENV = dict(os.environ)

# 项目根 = webui 的上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI = os.path.join(ROOT, "webui")
ENV_PATH = os.path.join(ROOT, ".env")
ENV_EXAMPLE = os.path.join(ROOT, ".env.example")
PROXIES_FILE = os.path.join(ROOT, "proxies.txt")  # WebUI 粘贴的代理池列表（textarea 存储）

sys.path.insert(0, WEBUI)
sys.path.insert(0, ROOT)
import scripts as schema  # noqa: E402


def _ensure_proxy_env():
    """把 CLASH_PROXY 注进本进程环境，让 requests(trust_env) 的接码 API 请求走代理；
    localhost API 直连(NO_PROXY)。"""
    proxy = ""
    try:
        proxy = _read_config_val("CLASH_PROXY", "http://127.0.0.1:10809")
    except Exception:
        proxy = "http://127.0.0.1:10809"
    if proxy and not os.environ.get("HTTPS_PROXY"):
        os.environ["HTTP_PROXY"] = os.environ["HTTPS_PROXY"] = proxy
        os.environ["http_proxy"] = os.environ["https_proxy"] = proxy
        os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost,::1"


app = FastAPI(title="Grok Register WebUI")

# 运行中的任务：run_id -> {proc, lines:[], done:bool, script, cmd, started}
RUNS = {}
_run_seq = [0]


# ============================================================ 配置/状态读取
def _read_config_val(key, default=""):
    """从环境/.env 读一个值。"""
    val = os.environ.get(key)
    if val:
        return val
    try:
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == key:
                    return v.strip().strip('"').strip("'") or default
    except Exception:
        pass
    return default


def _http_alive(url, timeout=3):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 500
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


# ============================================================ .env 读写(保留注释/顺序)
def _parse_env_file(path):
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _write_env_file(path, updates):
    """把 updates(dict) 写回 .env：已存在的行原地改值(保留注释/顺序)，新 key 追加到末尾。"""
    lines = []
    seen = set()
    if os.path.isfile(path):
        lines = open(path, encoding="utf-8").read().splitlines()
    out = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.partition("=")[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                seen.add(k)
                continue
        out.append(line)
    extra = [k for k in updates if k not in seen]
    if extra:
        out.append("")
        out.append("# ---- 由 WebUI 配置页新增 ----")
        for k in extra:
            out.append(f"{k}={updates[k]}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)


def _apply_saved_env(updates):
    """让当前 WebUI 与后续子进程看到新配置，同时保留启动前系统变量的优先级。"""
    for key, value in updates.items():
        if key in BOOT_ENV:
            continue
        if value == "":
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    if "CLASH_PROXY" in updates and "HTTPS_PROXY" not in BOOT_ENV:
        proxy = updates["CLASH_PROXY"].strip()
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            if proxy:
                os.environ[key] = proxy
            else:
                os.environ.pop(key, None)
    import importlib
    for name in ("config", "common.proxy_switch", "common.temp_email"):
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)


# ============================================================ 连通测试
def _direct_get(url, headers=None, timeout=8):
    """直连 GET(显式绕过代理——代理池控制口/本地服务都是 localhost)。"""
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers=headers or {})
    with opener.open(req, timeout=timeout) as r:
        return r.status, r.read(8192).decode("utf-8", "replace")


def _test_proxy():
    """测代理出口连通性：优先代理池控制口 /status，其次直接 curl 外网。"""
    ctrl = _read_config_val("PROXY_CTRL", "").strip().rstrip("/")
    if ctrl:
        try:
            code, body = _direct_get(ctrl + "/status", timeout=4)
            return True, f"代理池控制口连通 ✓ (HTTP {code}) {body[:60]}"
        except urllib.error.HTTPError as e:
            return True, f"代理池控制口在线 ✓ (HTTP {e.code})"
        except Exception as e:
            return False, f"连不上代理池控制口({ctrl})：{str(e)[:60]}。确认 relay 已启动"
    proxy = _read_config_val("CLASH_PROXY", "http://127.0.0.1:10809").strip()
    if not proxy:
        return False, "未配置出口代理(CLASH_PROXY)"
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    opener = urllib.request.build_opener(handler)
    try:
        with opener.open("https://api.ipify.org", timeout=8) as r:
            ip = r.read(64).decode("utf-8", "replace").strip()
        return True, f"代理出口连通 ✓ 出口IP={ip}"
    except Exception as e:
        return False, f"经代理访问外网失败：{str(e)[:70]}"


def _test_temp_email():
    """按当前 TEMP_EMAIL_PROVIDER 试建一个临时邮箱，验证 key 与 provider 配置。"""
    provider = _read_config_val("TEMP_EMAIL_PROVIDER", "remail").strip().lower()
    if provider == "custom":
        provider = "remail"  # custom 需完整配置，默认按 remail 验
    try:
        from common.temp_email import create_mailbox
        mb = create_mailbox(provider=provider)
        email = mb.get("email", "")
        if email:
            return True, f"{provider} 建号成功 ✓ {email}"
        return False, f"{provider} 建号返回空"
    except Exception as e:
        detail = str(e)[:160]
        hint = ""
        if provider == "remail" and ("REMAIL_API_KEY" in detail or "key" in detail.lower()):
            hint = "；请到配置页填写 REMAIL_API_KEY"
        elif provider == "yyds":
            hint = "；检查 YYDS_API_KEY"
        return False, f"{provider} 建号失败：{detail}{hint}"


_TESTERS = {
    "proxy": _test_proxy,
    "temp_email": _test_temp_email,
}


def _reload_config_modules():
    """重载 config 与依赖它的模块，让临时注入的环境变量立即生效。
    （temp_email 等模块在 import 时就把 config 值绑定为模块级常量，光改
    os.environ 不会更新它们，必须 reload。）"""
    import importlib
    for name in ("config", "common.temp_email"):
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)


@app.post("/api/test/{target}")
async def api_test(target: str, request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    overrides = (data or {}).get("env") or {}
    saved = {}
    allowed = set(schema.env_keys())
    for k, v in overrides.items():
        if k in allowed and v not in (None, ""):
            saved[k] = os.environ.get(k)
            os.environ[k] = str(v)
    try:
        _reload_config_modules()
        fn = _TESTERS.get(target)
        if not fn:
            return JSONResponse({"ok": False, "msg": f"未知测试目标: {target}"}, status_code=400)
        ok, msg = await asyncio.to_thread(fn)
        return {"ok": ok, "msg": msg}
    finally:
        for k, old in saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
        _reload_config_modules()


# ============================================================ API
@app.get("/api/scripts")
def api_scripts():
    return {"scripts": schema.SCRIPTS}


@app.get("/api/links")
def api_links():
    return {"links": getattr(schema, "EXTERNAL_LINKS", [])}


@app.get("/api/embeds")
def api_embeds():
    return {"embeds": []}


@app.get("/", response_class=HTMLResponse)
def index():
    return open(os.path.join(WEBUI, "static", "index.html"), encoding="utf-8").read()


@app.get("/api/status")
def api_status():
    proxy = _read_config_val("CLASH_PROXY", "http://127.0.0.1:10809")
    ctrl = _read_config_val("PROXY_CTRL", "")
    return {
        "pid": os.getpid(),
        "root": ROOT,
        "proxy": proxy,
        "proxy_ctrl_alive": bool(ctrl) and _http_alive(ctrl),
        "running": sum(1 for r in RUNS.values() if not r["done"]),
    }


@app.get("/api/env")
def api_env_get():
    cur = _parse_env_file(ENV_PATH)
    if not cur and os.path.isfile(ENV_EXAMPLE):
        cur = _parse_env_file(ENV_EXAMPLE)
    # PROXY_POOL_LIST 是 textarea，内容存 proxies.txt（不进 .env）
    pool_text = ""
    if os.path.isfile(PROXIES_FILE):
        try:
            pool_text = open(PROXIES_FILE, encoding="utf-8").read().rstrip("\n")
        except Exception:
            pool_text = ""
    groups = []
    for g in schema.ENV_SCHEMA:
        items = []
        for it in g["items"]:
            if it["key"] == "PROXY_POOL_LIST":
                value = pool_text
            else:
                value = cur.get(it["key"], "")
            items.append({
                "key": it["key"],
                "value": value,
                "required": it.get("required", False),
                "secret": it.get("secret", False),
                "help": it.get("help", ""),
                "default": it.get("default", ""),
                "type": it.get("type", "str"),
                "choices": it.get("choices", []),
            })
        groups.append({"group": g["group"], "tests": g.get("tests", []), "items": items})
    return {"groups": groups, "env_exists": os.path.isfile(ENV_PATH)}


@app.post("/api/env")
async def api_env_set(request: Request):
    data = await request.json()
    updates = data.get("env") or {}
    allowed = set(schema.env_keys())
    updates = {k: ("" if v is None else str(v)) for k, v in updates.items() if k in allowed}
    # PROXY_POOL_LIST 特殊处理：写 proxies.txt，不进 .env
    if "PROXY_POOL_LIST" in updates:
        pool_text = (updates.pop("PROXY_POOL_LIST") or "").strip("\r\n")
        try:
            with open(PROXIES_FILE, "w", encoding="utf-8") as f:
                f.write(pool_text + ("\n" if pool_text else ""))
        except Exception as e:
            return {"ok": False, "error": f"代理列表写入失败: {str(e)[:100]}"}
    if not os.path.isfile(ENV_PATH) and os.path.isfile(ENV_EXAMPLE):
        import shutil
        shutil.copy(ENV_EXAMPLE, ENV_PATH)
    _write_env_file(ENV_PATH, updates)
    _apply_saved_env(updates)
    return {"ok": True, "saved": len(updates) + (1 if "PROXY_POOL_LIST" in data.get("env") or {} else 0),
            "effective_now": True}


def _build_cmd(script, args):
    """把前端提交的 args(dict) 按 schema 拼成命令行 list。"""
    cmd = [sys.executable, "-u", os.path.join(ROOT, script["file"])]
    positional = []
    by_flag = {a["flag"]: a for a in script["args"]}
    for flag, spec in by_flag.items():
        if flag not in args:
            continue
        val = args[flag]
        typ = spec["type"]
        if spec.get("positional"):
            if val not in (None, "", []):
                positional.append(str(val))
            continue
        if typ == "bool":
            if val:
                cmd.append(flag)
        elif typ == "multi":
            if val:
                cmd.append(flag)
                cmd.extend(str(v) for v in val)
        else:
            if val not in (None, "", []):
                cmd.append(flag)
                cmd.append(str(val))
    cmd.extend(positional)
    return cmd


def _child_env():
    """构造新任务环境；保存后的 .env 无需重启 WebUI 即可生效。"""
    env = dict(os.environ)
    for key, value in _parse_env_file(ENV_PATH).items():
        if key not in BOOT_ENV:
            env[key] = value
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proxy = env.get("CLASH_PROXY", "http://127.0.0.1:10809").strip()
    if proxy:
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = proxy
        env["http_proxy"] = env["https_proxy"] = proxy
        env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost,::1"
    return env


@app.post("/api/run")
async def api_run(request: Request):
    data = await request.json()
    sid = data.get("script")
    args = data.get("args") or {}
    script = schema.script_by_id(sid)
    if not script:
        return JSONResponse({"error": f"未知脚本: {sid}"}, status_code=400)
    cmd = _build_cmd(script, args)
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=ROOT, env=_child_env(),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    _run_seq[0] += 1
    run_id = f"r{_run_seq[0]}"
    rec = {"proc": proc, "lines": [], "done": False, "stopped": False,
           "returncode": None, "script": sid,
           "cmd": " ".join(cmd), "started": time.strftime("%H:%M:%S")}
    RUNS[run_id] = rec

    async def _pump():
        try:
            async for raw in proc.stdout:
                rec["lines"].append(raw.decode("utf-8", "replace").rstrip("\n"))
                if len(rec["lines"]) > 5000:
                    rec["lines"] = rec["lines"][-4000:]
        except Exception as e:
            rec["lines"].append(f"[webui] 读取输出异常: {e}")
        finally:
            await proc.wait()
            rec["returncode"] = proc.returncode
            rec["done"] = True
            rec["lines"].append(f"[webui] 进程结束 exit={proc.returncode}")

    asyncio.create_task(_pump())
    return {"run_id": run_id, "cmd": rec["cmd"]}


@app.get("/api/logs/{run_id}")
async def api_logs(run_id: str):
    rec = RUNS.get(run_id)
    if not rec:
        return JSONResponse({"error": "无此任务"}, status_code=404)

    async def _stream():
        idx = 0
        while True:
            lines = rec["lines"]
            while idx < len(lines):
                yield f"data: {lines[idx]}\n\n"
                idx += 1
            if rec["done"] and idx >= len(rec["lines"]):
                result = json.dumps(
                    {"returncode": rec["returncode"], "stopped": rec["stopped"]},
                    ensure_ascii=False,
                )
                yield f"event: done\ndata: {result}\n\n"
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.post("/api/stop/{run_id}")
async def api_stop(run_id: str):
    rec = RUNS.get(run_id)
    if not rec:
        return JSONResponse({"error": "无此任务"}, status_code=404)
    if not rec["done"]:
        rec["stopped"] = True
        try:
            rec["proc"].terminate()
        except Exception:
            pass
    return {"ok": True}


_ensure_proxy_env()
app.mount("/static", StaticFiles(directory=os.path.join(WEBUI, "static")), name="static")
