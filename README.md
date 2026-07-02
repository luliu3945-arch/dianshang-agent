# 多 Agent 电商推荐与营销系统

基于 **Supervisor 编排模式** 的 Multi-Agent 系统：用户画像、商品推荐、营销文案、库存决策四个 Agent 协同工作，为每位用户生成"有货的、排好序的、带个性化文案的"推荐结果。

技术栈：`Python 3.11+` · `LangGraph` · `FastAPI` · `asyncio` · `Redis` · `Pydantic v2` · `Docker`

---

## 系统架构

```
用户请求 {"user_id": "u001", "num_items": 5}
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                Supervisor 编排器                      │
│                                                      │
│  Phase 1 (并行)                                      │
│  ┌────────────────┐      ┌────────────────┐         │
│  │  用户画像 Agent │      │  商品召回 Agent │         │
│  │  行为特征→RFM   │      │  多路召回+去重  │         │
│  └───────┬────────┘      └───────┬────────┘         │
│          │                       │                   │
│  Phase 2 (并行)                                      │
│  ┌────────────────┐      ┌────────────────┐         │
│  │  LLM 精排      │      │  库存决策 Agent │         │
│  │  画像×商品交叉  │      │  缺货过滤+限购  │         │
│  └───────┬────────┘      └───────┬────────┘         │
│          └───────────┬───────────┘                   │
│                      ▼                               │
│  Phase 3 (串行)                                      │
│  ┌──────────────────────────────────┐                │
│  │  结果聚合 → 营销文案 Agent        │                │
│  │  分群模板×LLM生成×广告法合规校验   │                │
│  └───────────────┬──────────────────┘                │
│                  ▼                                   │
│  ┌──────────────────────────────────┐                │
│  │  A/B 测试引擎                     │                │
│  │  哈希分桶 + Thompson Sampling     │                │
│  └───────────────┬──────────────────┘                │
└──────────────────┼───────────────────────────────────┘
                   ▼
     商品列表 + 个性化文案 + 实验分组
```

选择 Supervisor（中枢编排）而非 Handoffs（链式交接）：推荐流程固定且各阶段可并行，中枢统一做异常处理和结果聚合，端到端延迟 ≈ 各阶段最慢 Agent 之和，而非全部 Agent 之和。

## 四个 Agent

| Agent | 职责 | 关键实现 |
|-------|------|---------|
| 用户画像 `user_profile_agent` | 行为数据 → 结构化画像 | Redis Sorted Set 滑动窗口特征、RFM 模型、LLM 分群（新客/VIP/价格敏感/活跃/流失风险） |
| 商品推荐 `product_rec_agent` | 两阶段推荐 | 多路召回（协同过滤/向量/热度/新品）→ LLM 按画像精排 |
| 营销文案 `marketing_copy_agent` | 个性化文案 | 5 套分群 Prompt 模板 + LLM 生成 + 广告法违禁词过滤 |
| 库存决策 `inventory_agent` | 可售性守门 | 缺货剔除、低库存预警、按库存深度动态限购 |

## 核心设计

**并行编排**（`orchestrator/supervisor.py`）：`asyncio.gather()` 将无依赖的 Agent 分两批并行执行；同一套流程还有 LangGraph `StateGraph` 实现（`orchestrator/graph.py`），支持状态可视化与断点续跑，两种实现可通过不同 API 端点对比。

**可靠性**（`agents/base_agent.py`）：模板方法模式，基类统一封装计时、指数退避重试（tenacity）与降级 —— 任一 Agent 彻底失败时返回兜底结果而非抛异常，单点故障不拖垮整个推荐链路（如文案 Agent 挂掉时仍返回商品列表）。

**A/B 测试**（`services/ab_test.py`）：user_id MD5 哈希分桶保证同一用户实验期内始终命中同组；每组维护 Beta 分布参数，支持 Thompson Sampling 将流量向高转化组自动倾斜。

**实时特征**（`services/feature_store.py`）：Redis Sorted Set 以时间戳为 score 存储行为序列，O(log N) 支持 1h/24h/7d 滑动窗口统计与 RFM 打分。

## 快速开始

需要一个 OpenAI 兼容的 LLM API Key（阿里云百炼 / 智谱 / DeepSeek / 本地 Ollama 均可）。

```bash
cd python
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env      # 填入 ECOM_LLM_API_KEY（base_url/model 按需修改）
python main.py            # http://localhost:8000
```

调用推荐接口：

```bash
curl -X POST http://localhost:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "scene": "homepage",
    "num_items": 5,
    "context": {"recent_views": ["手机", "耳机"], "avg_order_amount": 500}
  }'
```

交互式 API 文档：`http://localhost:8000/docs`（Swagger 资源已替换为国内可达 CDN）。

也可以 Docker 一键启动（含 Redis / Milvus / MySQL）：

```bash
docker-compose up -d
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/recommend` | 推荐主接口（Supervisor 编排） |
| `POST` | `/api/v1/recommend/graph` | 同一流程的 LangGraph 实现 |
| `GET` | `/api/v1/experiments` | A/B 实验状态与分组指标 |
| `POST` | `/api/v1/experiments/{id}/outcome` | 回传转化结果，更新 Thompson Sampling 后验 |
| `GET` | `/api/v1/metrics` | 各 Agent 成功率 / 延迟统计 |
| `GET` | `/health` | 健康检查 |

响应示例（节选）：

```json
{
  "products": [
    {"product_id": "P001", "name": "iPhone 16 Pro", "category": "手机", "price": 7999.0}
  ],
  "marketing_copies": [
    {"product_id": "P001", "copy": "全新 iPhone 16 Pro 旗舰登场！钛金属质感拉满，随手一拍即是大片。"}
  ],
  "experiment_group": "control",
  "total_latency_ms": 1523.4
}
```

## 项目结构

```
├── docker-compose.yml            # API + Redis + Milvus + MySQL
├── docs/architecture.md          # 架构设计详解
└── python/
    ├── main.py                   # FastAPI 入口
    ├── agents/
    │   ├── base_agent.py         # 基类：重试 / 降级 / 指标
    │   ├── user_profile_agent.py
    │   ├── product_rec_agent.py
    │   ├── marketing_copy_agent.py
    │   └── inventory_agent.py
    ├── orchestrator/
    │   ├── supervisor.py         # asyncio 并行编排（主路径）
    │   └── graph.py              # LangGraph StateGraph 实现
    ├── services/
    │   ├── ab_test.py            # 分桶 + Thompson Sampling
    │   ├── feature_store.py      # Redis 实时特征
    │   └── metrics.py            # 监控指标收集
    ├── models/schemas.py         # Pydantic 数据模型
    ├── config/settings.py        # 环境变量配置
    └── tests/                    # 单元测试
```

运行测试：

```bash
python tests/test_ab_test.py
```

## 当前边界与规划

- 商品召回目前使用内置示例数据，Milvus 向量检索与 MySQL 库存接入为下一阶段目标（代码中已预留注入点）
- 特征存储已实现 Redis 读写逻辑，未配置 Redis 时自动回退到请求上下文
- 规划中：推荐结果缓存、Prompt 压缩降延迟、Prometheus 指标导出
