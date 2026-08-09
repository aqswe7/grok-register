"""
本地代理池转发器 v2：监听 127.0.0.1:10809，从代理池文件中轮换 IP。
每 ROTATE_EVERY 个 CONNECT 请求自动切换到下一个代理。
解决 Chromium 不支持 HTTP 代理 URL 认证的问题。

可配置项（同目录 .env，或环境变量）：
  POOL_FILE         代理池文件路径（每行 user:pass@host:port），默认同目录 miyaip_pool.txt
  RELAY_PORT        出口代理监听端口，默认 10809
  RELAY_CTRL_PORT   控制口端口(/status /rotate /next)，默认 10810
"""
import base64
import os
import socket
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


def _load_dotenv(path=None):
    """零依赖 .env 读取器：只在 os.environ 尚未设置时填入。"""
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(os.environ.get("RELAY_PORT", "10809") or "10809")
CTRL_PORT = int(os.environ.get("RELAY_CTRL_PORT", "10810") or "10810")
# 代理池文件优先级：显式 POOL_FILE > WebUI 粘贴的 proxies.txt > 默认 miyaip_pool.txt
POOL_FILE = os.environ.get("POOL_FILE", "") or (
    os.path.join(BASE_DIR, "proxies.txt")
    if os.path.isfile(os.path.join(BASE_DIR, "proxies.txt"))
    else os.path.join(BASE_DIR, "miyaip_pool.txt")
)
ROTATE_EVERY = 500  # 每号安全阈值（~1次浏览器注册的请求量）

# ============================================================
# 加载代理池
# ============================================================
proxies = []
if not os.path.isfile(POOL_FILE):
    print(f"[proxy-relay] 代理池文件不存在: {POOL_FILE}")
    print("[proxy-relay] 请放置代理列表(每行 user:pass@host:port)，或从 WebUI 配置页粘贴代理列表后重启。")
    sys.exit(1)
with open(POOL_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 格式: user:pass@host:port
        try:
            auth, host_port = line.rsplit("@", 1)
            user, pwd = auth.split(":", 1)
            host, port = host_port.rsplit(":", 1)
            proxies.append({
                "host": host,
                "port": int(port),
                "user": user,
                "pass": pwd,
                "auth_b64": base64.b64encode(f"{user}:{pwd}".encode()).decode(),
            })
        except Exception:
            print(f"[proxy-relay] 跳过无法解析的行: {line[:60]}")
if not proxies:
    print(f"[proxy-relay] 代理池文件为空或全部无效: {POOL_FILE}")
    sys.exit(1)

pool_lock = threading.Lock()
current_idx = 0
conn_count = 0


def get_current_proxy():
    global current_idx, conn_count
    with pool_lock:
        conn_count += 1
        if conn_count >= ROTATE_EVERY:
            current_idx = (current_idx + 1) % len(proxies)
            conn_count = 0
            p = proxies[current_idx]
            print(f"[rotate] 切换代理 #{current_idx+1}/{len(proxies)}: {p['host']}")
        return proxies[current_idx]


def handle_client(client_sock):
    try:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = client_sock.recv(4096)
            if not chunk:
                return
            data += chunk
            if len(data) > 8192:
                return

        first_line = data.split(b"\r\n")[0].decode(errors="ignore")
        if not first_line.startswith("CONNECT"):
            client_sock.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return

        target = first_line.split()[1]

        proxy = get_current_proxy()
        upstream_sock = socket.create_connection((proxy["host"], proxy["port"]), timeout=10)

        connect_req = (
            f"CONNECT {target} HTTP/1.1\r\n"
            f"Host: {target}\r\n"
            f"Proxy-Authorization: Basic {proxy['auth_b64']}\r\n"
            f"\r\n"
        ).encode()
        upstream_sock.sendall(connect_req)

        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = upstream_sock.recv(4096)
            if not chunk:
                upstream_sock.close()
                return
            resp += chunk

        status_line = resp.split(b"\r\n")[0].decode(errors="ignore")
        if "200" not in status_line:
            client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            upstream_sock.close()
            return

        client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        def pipe(src, dst):
            try:
                while True:
                    d = src.recv(8192)
                    if not d:
                        break
                    dst.sendall(d)
            except Exception:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

        t1 = threading.Thread(target=pipe, args=(client_sock, upstream_sock), daemon=True)
        t2 = threading.Thread(target=pipe, args=(upstream_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=300)
        t2.join(timeout=300)

    except Exception:
        pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass


def start_ctrl():
    class CtrlHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            global current_idx, conn_count
            if self.path == "/rotate":
                with pool_lock:
                    old = current_idx
                    current_idx = (current_idx + 1) % len(proxies)
                    conn_count = 0
                    ip = proxies[current_idx]['host']
                self.send_response(200); self.end_headers()
                self.wfile.write(f'{{"ok":true,"from":{old+1},"to":{current_idx+1},"ip":"{ip}"}}'.encode())
            elif self.path == "/next":
                # 返回下一个代理的完整连接串（含认证），供并发注册每号分配独立 IP。
                with pool_lock:
                    current_idx = (current_idx + 1) % len(proxies)
                    conn_count = 0
                    p = proxies[current_idx]
                proxy_url = f"http://{p['user']}:{p['pass']}@{p['host']}:{p['port']}"
                self.send_response(200); self.end_headers()
                self.wfile.write(
                    f'{{"ok":true,"idx":{current_idx+1},"total":{len(proxies)},"proxy":"{proxy_url}","ip":"{p["host"]}"}}'.encode()
                )
            elif self.path == "/status":
                with pool_lock:
                    ip = proxies[current_idx]['host']
                self.send_response(200); self.end_headers()
                self.wfile.write(f'{{"idx":{current_idx+1},"total":{len(proxies)},"req":{conn_count},"ip":"{ip}"}}'.encode())
            else:
                self.send_response(404); self.end_headers()
        def log_message(self, format, *args): pass
    srv = HTTPServer(("127.0.0.1", CTRL_PORT), CtrlHandler)
    print(f"[proxy-ctrl] http://127.0.0.1:{CTRL_PORT}")
    srv.serve_forever()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(50)
    print(f"[proxy-relay] {LISTEN_HOST}:{LISTEN_PORT} | 代理池: {len(proxies)} 个")
    print(f"[proxy-relay] 轮换频率: 每 {ROTATE_EVERY} 个请求")
    print(f"[proxy-relay] 当前代理: #{1}/{len(proxies)} {proxies[0]['host']}")
    threading.Thread(target=start_ctrl, daemon=True).start()
    try:
        while True:
            client, addr = server.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[proxy-relay] 关闭")
    finally:
        server.close()


if __name__ == "__main__":
    main()
