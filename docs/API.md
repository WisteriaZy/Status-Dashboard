# API 接口文档

## 基础信息

- Base URL: `http://127.0.0.1:8000`
- 数据格式: JSON

---

## 通用响应结构

所有 API 响应遵循以下结构：

```json
{
  "status": "ok" | "error",
  "data": { ... },
  "message": "可选的消息"
}
```

---

## 接口列表

### GET /api/health

健康检查

**响应:**
```json
{
  "status": "ok",
  "message": "服务运行中"
}
```

---

### GET /api/status

获取当前设备状态

**响应:**
```json
{
  "current_app": {
    "name": "应用名称",
    "title": "窗口标题",
    "icon": "图标路径或null"
  },
  "device": {
    "cpu_percent": 25.5,
    "memory_percent": 60.2,
    "uptime_seconds": 3600
  }
}
```

---

## 待实现接口

- `GET /api/apps/usage` - 应用使用时长统计
- `GET /api/todos` - 获取任务列表
- `POST /api/todos/{id}/complete` - 完成任务
- `GET /api/stats` - 获取统计数据
