# 🤖 Grok 注册机（独立版）

Grok (x.ai) **纯 HTTP 协议**批量注册工具：临时邮箱收验证码 → Turnstile 打码 → 建号 → 取 sso token。
支持注册后自动导入 SUB2API Grok 分组。带本地 Web 面板，所有配置（临时邮箱 / 打码平台 / 代理池 / SUB2API）都可在网页里填写，**无需改代码**，适配不同用户的账号体系。

> 本工具从 reg-factory 项目独立而来，只保留 Grok 注册链路，开箱即用。

---

## 一、功能特性

- ✅ 纯 HTTP 协议注册（无浏览器），速度快、支持并发（默认每号独立代理 IP）
- ✅ 临时邮箱多 provider：**ReMail（主推）/ YYDS / GPTMail / MoeMail / CFMail / 自定义**
- ✅ 打码平台：**CapSolver（主推）/ EZ-Captcha / YesCaptcha**，失败自动切换 + 快速重试
- ✅ 建号成功但 sso 未取到时自动落盘 `tokens/grok/pending/`，账号不浪费
- ✅ Web 面板配置 + 连通测试 + 实时日志，全程可视化

## 二、目录结构

```
grok-register-standalone/
├── start.bat            # 双击启动（自动拉起代理池 + 打开面板 http://127.0.0.1:8799）
├── install.bat          # 一键安装（建 venv + 装依赖）
├── requirements.txt     # Python 依赖
├── .env.example         # 配置模板（复制为 .env 填写）
├── config.py            # 配置读取（自动加载 .env）
├── register_grok_http.py# 注册机主程序（也可命令行单独跑）
├── proxy_relay.py       # 本地代理池转发器（10809 出口 / 10810 控制口，start.bat 自动拉起）
├── miyaip_pool.txt      # 代理 IP 池（每行一个 user:pass@host:port，可自行替换）
├── xconsole_client/     # x.ai 协议客户端（不用动）
├── common/              # 公共模块：临时邮箱/打码/上传（不用动）
├── webui/               # Web 面板（后端 + 前端）
├── tokens/              # 产出目录：grok/*.sso.json + grok/pending/*.json
└── README.md            # 本教程
```

## 三、环境准备（你需要先有）

| 项 | 说明 | 必需 |
|---|---|---|
| **Python 3.10+** | 官方安装时勾选 "Add Python to PATH" | ✅ |
| **出口代理** | 能访问 x.ai 的代理。推荐本地代理池 relay（配好的动态 IP 池），或 Clash 等 | ✅ |
| **临时邮箱账号** | ReMail（付费，主推）/ YYDS / GPTMail 任一个的 API key | ✅ |
| **打码平台账号** | CapSolver / EZ-Captcha / YesCaptcha 任一个的 API key + 余额 | ✅ |
| SUB2API 账号 | 可选，用于注册后自动导入 Grok 分组 | ⭕ |

各平台注册地址：
- **ReMail**：https://remail.aishop6.com （后台获取 `rk-` 开头 key）
- **CapSolver**：https://dashboard.capsolver.com （注册充值，`CAP-` 开头 key，充值几美元够跑几百个号）
- **EZ-Captcha**：https://www.ez-captcha.com
- **YesCaptcha**：https://yescaptcha.com

## 四、安装与启动

```bat
:: 1. 双击 install.bat（首次，建 venv + 装依赖，等它跑完）
:: 2. 双击 start.bat（自动拉起代理池 relay + 启动面板，浏览器自动打开 http://127.0.0.1:8799）
```

> **代理池自动管理（三态）**：start.bat 启动时会检测控制口，未运行则自动用本目录 relay 拉起。代理来源按优先级：
> 1. WebUI 配置页「代理出口」粘贴的列表（保存后写入 `proxies.txt`，**推荐**——人人可用自己的代理）
> 2. 本目录 `miyaip_pool.txt`（每行 `user:pass@host:port`，直接替换文件也行）
> 3. 不用内置代理池：`CLASH_PROXY` 填 Clash 端口、`PROXY_CTRL` 留空 → 单出口运行

命令行方式（可选，跳过面板）：

```bat
.venv\Scripts\python.exe register_grok_http.py --count 2 --concurrency 1
```

## 五、Web 面板使用

### 第 1 步：配置页（⚙️ 配置 .env）

左侧点「配置 (.env)」，按分组填写并**点右上角「保存配置」**：

| 分组 | 填什么 |
|---|---|
| **临时邮箱** | `TEMP_EMAIL_PROVIDER` 选 remail（或你的 provider）；`REMAIL_API_KEY` 填 rk- 开头 key；`REMAIL_PROJECT_ID`/`PRODUCT_ID` 按你后台的库存（Grok 默认 3/8） |
| **打码平台** | `CAPSOLVER_API_KEY` 必填（CAP- 开头）；EZ/YesCaptcha 可选（CapSolver 失败时自动切换） |
| **代理出口** | `CLASH_PROXY` 出口地址（默认内置 relay 10809）；`PROXY_CTRL` 控制口（默认 10810）；`PROXY_POOL_LIST` 粘贴你自己的代理列表（每行 `user:pass@host:port`，保存后 relay 自动改用它，写入本目录 `proxies.txt`）；`RELAY_PORT`/`RELAY_CTRL_PORT` 内置 relay 端口 |
| **SUB2API** | 可选。填 `SUB2API_URL` + 账密 或 `SUB2API_ADMIN_KEY`，`SUB2API_GROK_GROUP` 是目标分组名 |
| **高级调优** | `GROK_CAP_RETRIES` 打码重试次数（默认 3，打码频繁 600010 时可调 5-8） |

> 保存后新任务立即生效，无需重启面板。

每个配置组右上角有**连通测试**按钮：
- 临时邮箱组「测试建号」→ 用当前配置实际建一个临时邮箱验证 key 有效
- 代理组「测试代理」→ 验证代理池控制口 / 出口连通性

### 第 2 步：运行任务（▶ 运行任务）

左侧点「Grok 注册」，填参数：

| 参数 | 说明 | 建议 |
|---|---|---|
| `--count` | 注册总数 | 先跑 2 个验证，再上批量 |
| `--concurrency` | 并发数（每号自动分配独立 IP） | **4-8**（ReMail 平台上限约 10） |
| `--provider` | 临时邮箱来源 | 留空 = 用配置页的 TEMP_EMAIL_PROVIDER |
| `--sub2api` | 勾选 = 注册成功后导入 SUB2API | 按需 |
| `--sub2api-group` | SUB2API 分组名 | 留空取配置 |
| `--node` | Clash 节点 | 留 auto；不开 Clash 自动走代理池 |

点「▶ 运行」，下方实时滚动日志，可随时「停止」。

### 产出文件

- 成功：`tokens/grok/<email>.sso.json` → 这就是可用的 Grok 登录态（sso cookie），sub2api 导入用
- 建号成功但 sso 未取到：`tokens/grok/pending/<email>.json`（含密码，可后续补 sso）
- 日志里出现 `[OK] grok sso token 已保存` 即成功

## 六、命令行方式（不用面板时）

```bat
:: 跑 2 个号验证（串行）
.venv\Scripts\python.exe register_grok_http.py --count 2 --concurrency 1

:: 批量 160（8 并发 + 上传 sub2api）
.venv\Scripts\python.exe register_grok_http.py --count 160 --concurrency 8 --sub2api

:: 指定临时邮箱 provider（逗号分隔可故障转移）
.venv\Scripts\python.exe register_grok_http.py --count 10 --provider remail,yyds

:: 调大打码重试次数（打码频繁被风控时）
set GROK_CAP_RETRIES=5
.venv\Scripts\python.exe register_grok_http.py --count 10 --concurrency 4
```

## 七、常见问题（FQA，均为实战排障经验）

### 1. 大量报 `Bot behavior detected, error code:600010`
- **原因**：CapSolver 每次打码随机分配它自己的服务端节点，部分节点已被 x.ai 的 Cloudflare 标记（报 600010），属于"撞运气"，不是你的配置错。
- **解决**：
  1. 把 `GROK_CAP_RETRIES` 调到 5-8（快速重试，每次换节点，成功率从 ~1/3 提到 70%+）
  2. 在配置页加配 EZ-Captcha / YesCaptcha key（CapSolver 失败自动切换）
  3. 确认代理 IP 干净（见下条）

### 2. 页面 `HTTP 403` 或建号返回 71 字节空响应
- **原因**：该代理 IP 被 Cloudflare 标记（部分动态 IP 池是"混合"的：有的干净有的脏）。
- **解决**：换一批新 IP（重新生成代理池）；或换线路/地区；并发建议 4-8 不要太高。

### 3. 建号成功但 `未取到 sso token`
- 现在会先落盘 `tokens/grok/pending/`，账号不丢。
- 常见原因：建号响应的 RSC body 太短（空响应误判已修复，会直接判失败而不是白等）；或 IP 半干不净导致会话被降级。
- 换干净 IP 后重跑即可；已 pending 的账号可稍后写脚本用密码登录补 sso。

### 4. CreateSession 报 `invalid-credentials`
- 大概率是**账号实际没建成**（建号空响应被拒），不是密码错。对照上一条：看日志 `create_account body 预览` 那行是不是很短（几十字节）——短 = 被拒，换 IP 重试。

### 5. 打码重试后第 2 次起报 `Failed to verify Cloudflare turnstile token`
- 已修复：Turnstile token 是一次性的，现在每次重试都会重新解新 token。旧版才有此问题。

### 6. 代理池（relay）怎么启动
- 双击 `start.bat` 会自动检测并拉起本目录的 relay（10809/10810），**一般不用手动操作**。
- 手动启动（或 relay 异常时）：
```bat
cd D:\projects\grok-register-standalone
.venv\Scripts\python.exe proxy_relay.py
```
- 验证：浏览器开 `http://127.0.0.1:10810/status`，`total` 应为 `miyaip_pool.txt` 的行数。

### 7. remail 收不到验证码
- 检查 `REMAIL_API_KEY` 是否有效（配置页「测试建号」）；项目 ID/产品 ID 是否与你后台一致（Grok 默认 project=3/product=8，不同账号可能不同）；余额是否充足。

### 8. 并发多少合适
- 建议 4-8。ReMail 平台并发上限约 10，超过会报错；并发过高也更容易触发 x.ai 风控（建号空响应变多）。

## 八、合规提示

本工具仅供学习研究 API 交互与自动化流程使用。批量注册行为可能违反 x.ai 的服务条款，请自行评估风险，遵守当地法律法规与平台规则，勿用于任何违规用途。打码/接码/代理产生的费用由使用者自行承担。

---

*基于 reg-factory 项目 Grok 注册链路独立化整理，2026-08-09。*
