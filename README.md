# Autism Crawler（自闭症内容爬虫）

自动采集与自闭症相关的学术论文、社区讨论、新闻资讯，并存入 PostgreSQL 数据库，支持向量语义搜索。

---

## 系统架构概览

```
config/surfaces.json
        │
        ▼
   Scheduler（调度器）
   每分钟检查一次，按各数据源的配置间隔触发采集
        │
        ├─► Collector（采集器）× 16 种平台
        │       Reddit / RSS / PubMed / Europe PMC /
        │       Semantic Scholar / CrossRef / bioRxiv /
        │       DOAJ / OpenAlex / ClinicalTrials /
        │       CORE / Wikipedia / Hacker News /
        │       YouTube / NewsAPI / HTML 爬虫
        │
        ▼
   Pipeline（入库管道）
   URL 去重 upsert → crawled_items 表
        │
        ▼
   Embedding Loop（向量化循环）
   每 15 分钟批量调用 OpenAI text-embedding-3-small
   将标题 + 摘要转为 1536 维向量，写入 pgvector
        │
        ▼
   PostgreSQL + pgvector
   表：crawled_items / surfaces / http_cache
```

---

## 核心组件说明

### 1. 数据源配置（`config/surfaces.json`）

每个数据源称为一个 **Surface（采集面）**，配置项包括：

| 字段 | 说明 |
|------|------|
| `key` | 唯一标识，如 `pubmed_autism` |
| `platform` | 采集器类型，如 `pubmed`、`reddit` |
| `poll_interval_sec` | 采集间隔（秒） |
| `max_items` | 每次最多采集条数 |
| `config` | 平台专属参数（subreddit 名称、API 查询词等） |

首次启动时，调度器自动将 `surfaces.json` 写入数据库，后续可通过 Django 管理后台直接启停或调整。

---

### 2. 调度器（`src/scheduler.py`）

- 每 **60 秒** 检查所有已启用的 Surface
- 若距上次运行时间 ≥ `poll_interval_sec`，则触发对应采集器
- 所有 Surface 的采集任务**并发执行**（`asyncio.gather`）
- 每次运行后更新 `last_run_at`、`last_status`、`last_error`、`consecutive_fails`

---

### 3. 采集器（`src/collectors/`）

每个采集器实现统一接口：

```python
async def collect(config, cursor, limit) -> tuple[list[CollectedItem], next_cursor]
```

- `cursor`：分页游标，支持断点续采
- 返回标准化的 `CollectedItem`（标题、URL、摘要、作者、DOI、发布时间等）

**16 种平台对应的采集策略：**

| 类型 | 平台 |
|------|------|
| 学术 API | PubMed、Europe PMC、Semantic Scholar、CrossRef、bioRxiv/medRxiv、DOAJ、OpenAlex、CORE |
| 临床数据 | ClinicalTrials.gov |
| 社区 | Reddit（多个子版块）、Hacker News |
| 媒体 | RSS 订阅源、NewsAPI、YouTube |
| 百科 | Wikipedia |
| 网页爬取 | HTML 爬虫（JSON-LD → Open Graph → CSS 选择器，逐级降级） |

---

### 4. 入库管道（`src/pipeline.py`）

- 以 **URL 为唯一键**，执行 PostgreSQL upsert（`ON CONFLICT DO UPDATE`）
- 重复 URL 只更新 `engagement`、`rank_position` 等动态字段，不重复插入
- DOI 唯一索引冲突（同一论文不同 URL）自动跳过
- 通过 **Unpaywall API** 补充开放获取状态

---

### 5. 向量化循环（`src/embeddings.py`）

- 每 **15 分钟**运行一次，处理尚未向量化的条目（每批最多 500 条）
- 将 `title + description[:500]` 拼接后调用 OpenAI `text-embedding-3-small`
- 生成的 1536 维向量存入 `crawled_items.embedding`（pgvector 类型）
- 未配置 `OPENAI_API_KEY` 时自动跳过，不影响爬虫主流程

---

## 数据库表结构

### `crawled_items` — 采集内容

| 字段 | 说明 |
|------|------|
| `id` | 自增主键 |
| `url` | 唯一索引，去重依据 |
| `title` / `description` / `content_body` | 标题、摘要、正文 |
| `source` / `surface_key` | 来源平台和采集面标识 |
| `doi` / `journal` / `open_access` | 学术论文专属字段 |
| `authors_json` | 作者列表（JSONB） |
| `engagement` | 互动数据（点赞数等，JSONB） |
| `embedding` | 1536 维语义向量（pgvector） |
| `collected_at` | 入库时间 |

### `surfaces` — 采集面状态

记录每个数据源的运行状态，可通过 Django 后台管理。

### `http_cache` — HTTP 缓存

存储 ETag / Last-Modified，支持条件请求，减少重复流量。

---

## 快速启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DATABASE_URL、API 密钥等

# 2. 安装依赖（含 Django 管理后台）
pip install -r requirements.txt

# 3. 运行管理菜单
bash setup.sh
```

**管理菜单选项：**

| 选项 | 功能 |
|------|------|
| 1 | 启动/重启 爬虫 + Django 管理后台 |
| 2 | 查看服务运行状态 |
| 3 | 执行数据库迁移（Alembic + Django） |
| 4 | 显示管理后台地址 |
| 5 | 创建 Django 超级用户 |

---

## Django 管理后台

后台运行于 **http://localhost:8001/admin/**，提供：

- **Surface 监控**：各数据源的运行状态、最近错误、连续失败次数，可直接启停
- **内容浏览**：按来源/平台筛选已采集内容，支持标题、DOI、作者搜索
- **HTTP 缓存**：查看缓存状态

首次使用需先通过菜单选项 5 创建超级用户。

---

## 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | ✅ | asyncpg 连接串，供爬虫使用 |
| `DATABASE_URL_SYNC` | ✅ | psycopg2 连接串，供 Django 使用 |
| `OPENAI_API_KEY` | ☑️ 可选 | 填写后启用语义向量化 |
| `REDDIT_CLIENT_ID/SECRET` | ☑️ 可选 | Reddit API 凭证 |
| `PUBMED_API_KEY` | ☑️ 可选 | 提升 PubMed 请求频率上限 |
| `NEWSAPI_KEY` | ☑️ 可选 | NewsAPI 访问密钥 |
| `YOUTUBE_API_KEY` | ☑️ 可选 | YouTube Data API 密钥 |
| `CRAWLER_EMAIL` | ☑️ 可选 | 礼貌池标识（CrossRef、OpenAlex） |

---

## 技术栈

- **Python 3.9+**，全程异步（`asyncio` + `asyncpg`）
- **SQLAlchemy 2.0**（异步 ORM）+ **Alembic**（数据库迁移）
- **PostgreSQL 15** + **pgvector**（向量相似度搜索）
- **httpx**（HTTP 客户端，支持速率限制与随机延迟）
- **Django 4.2**（管理后台，`managed=False` 复用现有表）
- **OpenAI API**（文本向量化）
