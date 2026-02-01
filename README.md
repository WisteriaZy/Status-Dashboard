# Local Device Status Dashboard

本地设备状态面板 - 用于监控 Windows 设备状态、管理任务、接收提醒通知。

## 功能

- **设备状态监控**: CPU、内存、磁盘使用率，运行时间
- **活动窗口追踪**: 当前活动应用和窗口标题
- **移动设备状态**: 接收手机状态推送（通过 AutoX.js）
- **本地 TODO 系统**: 任务管理、定时/循环提醒
- **多渠道通知**: Windows 系统通知、QQ 私聊/群消息
- **MCP Server**: 让 LLM 通过 MCP 协议管理任务
- **2FA 认证**: TOTP 两步验证保护隐私
- **SMTC 支持**: 媒体信息获取

## 项目结构

```
0LookingZy/
├── backend/                # 后端代码
│   ├── main.py            # FastAPI 主服务 (端口 8000)
│   ├── mcp_server.py      # MCP Server (端口 8002)
│   ├── config.py          # 配置加载模块
│   ├── local_todo.py      # TODO 系统
│   ├── auth.py            # TOTP 认证
│   ├── qq_notify.py       # QQ 通知
│   ├── mobile_device.py   # 移动设备状态
│   ├── window_tracker.py  # 窗口追踪
│   ├── device_info.py     # 设备信息
│   ├── media_info.py      # 媒体信息
│   ├── screenshot.py      # 截图
│   ├── requirements.txt   # 主服务依赖
│   └── requirements-mcp.txt  # MCP Server 依赖
├── frontend/              # 前端页面
├── config/                # 配置文件
│   ├── config.yaml        # 主配置文件
│   ├── totp_secret.txt    # TOTP 密钥 (自动生成)
│   └── device_secret.txt  # 设备推送密钥 (自动生成)
├── data/                  # 数据存储
│   └── todos.json         # TODO 数据
├── mcp_venv/              # MCP Server 独立虚拟环境
├── docs/                  # 文档
│   └── API.md             # API 接口文档
├── start_mcp.bat          # MCP Server 启动脚本
└── README.md              # 本文件
```

## 快速开始

### 1. 安装主服务依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置

编辑 `config/config.yaml`，设置：

- QQ 通知的 WebSocket 地址和 Token
- 通知目标（私人/公共）
- 其他可选配置

### 3. 启动主服务

```bash
cd backend
python main.py
```

访问 http://127.0.0.1:8000

首次访问需要 2FA 验证，扫描 `config/totp_qrcode.png` 二维码添加到认证器。

### 4. (可选) 启动 MCP Server

MCP Server 使用独立虚拟环境，避免依赖冲突。

首次设置：
```bash
python -m venv mcp_venv
mcp_venv\Scripts\pip install -r backend/requirements-mcp.txt
```

启动：
```bash
# 方式一：使用启动脚本
start_mcp.bat

# 方式二：手动启动
mcp_venv\Scripts\python backend/mcp_server.py
```

MCP 端点: `http://localhost:8002/mcp`

## 配置说明

`config/config.yaml` 配置项：

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `server.host` | 主服务监听地址 | `127.0.0.1` |
| `server.port` | 主服务端口 | `8000` |
| `server.mcp_host` | MCP Server 监听地址 | `0.0.0.0` |
| `server.mcp_port` | MCP Server 端口 | `8002` |
| `auth.app_name` | TOTP 应用名 | `LocalDashboard` |
| `auth.token_valid_days` | Token 有效期(天) | `7` |
| `mobile_device.timeout_seconds` | 设备离线超时(秒) | `60` |
| `reminder.check_interval` | 提醒检查间隔(秒) | `30` |
| `qq_notify.ws_url` | NapCat WebSocket 地址 | - |
| `qq_notify.token` | NapCat Token | - |
| `qq_notify.targets` | 通知目标映射 | - |

## MCP Tools

MCP Server 提供以下工具供 LLM 调用：

| Tool | 说明 | 参数 |
|------|------|------|
| `list_tasks` | 列出任务 | `include_completed: bool` |
| `add_task` | 创建任务 | `title, important, notes, remind, remind_tag` |
| `complete_task` | 完成任务 | `task_id` |
| `delete_task` | 删除任务 | `task_id` |
| `update_task` | 更新任务 | `task_id, title, notes, important, remind, remind_tag` |

### remind 参数格式

```python
# 一次性提醒
{"type": "once", "at": "2026-01-31T14:30"}

# 每天提醒
{"type": "daily", "hours": [9, 14, 18]}

# 每周提醒 (1=周一, 7=周日)
{"type": "weekly", "weekdays": [1, 3, 5], "hour": 9}

# 每月提醒
{"type": "monthly", "days": [1, 15], "hour": 9}
```

## AstrBot 配置

在 AstrBot 管理面板添加 MCP Server：

```json
{
  "transport": "streamable_http",
  "url": "http://<Windows_IP>:8002/mcp",
  "headers": {},
  "timeout": 5,
  "sse_read_timeout": 300
}
```

## API 文档

详见 [docs/API.md](docs/API.md)

## 开发原则

- 最小可用优先（MVP）
- 每一步必须可运行、可观察
- 一次只解决一个问题
- 本地优先，不依赖云服务

## License

MIT

---
By Claude Code
