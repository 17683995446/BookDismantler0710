# Book Dismantler

> AI 驱动的开源拆书工具：将电子书拆解为思维导图、知识卡片、信息图、结构化笔记等多种知识形态。

## 特性

- **多格式输入**：支持 PDF、EPUB
- **多 LLM 后端**：OpenAI、DeepSeek、Gemini、Ollama（本地部署）
- **6 种知识产物**：
  - Markdown 结构化笔记
  - Org-mode 笔记
  - 思维导图（markmap，可交互 SVG）
  - 知识卡片（HTML 卡片组，含侧边导航）
  - 信息图（概念矩阵 + 关系网络摘要）
  - 概念剖析图（6 维度深度解析）
- **Web UI**：浏览器上传、配置、触发任务、预览下载
- **CLI**：命令行一键拆书，支持管道式分步操作
- **Docker 部署**：一键容器化运行

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your/book-dismantler.git
cd book-dismantler

# 安装（含开发依赖）
pip install -e ".[dev,web,export]"

# 或仅安装核心功能
pip install -e ".[web]"
```

### 配置

复制 `.env.example` 为 `.env`，填入你的 LLM API Key：

```bash
cp .env.example .env
# 编辑 .env，至少配置一个 provider 的 API Key
```

### CLI 使用

```bash
# 一键拆书
book-dismantler dismantle book.pdf --provider deepseek --model deepseek-chat

# 仅解析文档
book-dismantler parse book.pdf -o parsed.json

# 仅执行 AI 分析（需先解析）
book-dismantler analyze parsed.json -o knowledge.json

# 仅渲染产物（需先分析）
book-dismantler render knowledge.json -o ./output

# 列出可用 Provider
book-dismantler providers list

# 测试 Provider 连通性
book-dismantler providers test --provider deepseek

# 启动 Web 服务
book-dismantler serve --port 8000
```

### Web UI 使用

```bash
# 启动服务
book-dismantler serve

# 或使用 uvicorn 直接启动
uvicorn book_dismantler.api.app:create_app --factory --port 8000
```

浏览器打开 `http://localhost:8000`，即可：
1. 上传 PDF/EPUB 文件
2. 选择 LLM Provider 和模型
3. 创建拆书任务
4. 查看任务状态和产物
5. 预览和下载产物

### Docker 部署

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

## 架构

```
┌─────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)               │
│              Web UI (HTML/CSS/JS)                    │
├─────────────────────────────────────────────────────┤
│              Application Layer (Runner)              │
│           CLI (Typer)    │    Jobs (状态机)           │
├─────────────────────────────────────────────────────┤
│  Export Layer    │         Rendering Layer            │
│  PNG / HTML /    │  Markdown │ OrgMode │ Mindmap     │
│  Bundler         │  Cards │ Infographic │ Anatomy   │
├──────────────────┴──────────────────────────────────┤
│           Analysis Layer (Pipeline)                   │
│  Outline │ Concepts │ Relationships │ Anatomy        │
│              Aggregator (跨块合并)                     │
├─────────────────────────────────────────────────────┤
│              LLM Layer (统一抽象)                      │
│    OpenAI │ DeepSeek │ Gemini │ Ollama               │
│         (OpenAI SDK + base_url 统一接入)              │
├─────────────────────────────────────────────────────┤
│            Parsing Layer (解析器)                      │
│      PDF Parser │ EPUB Parser │ Chunker              │
├─────────────────────────────────────────────────────┤
│             Domain Layer (核心模型)                    │
│  Document │ Chunk │ KnowledgeModel │ Concept          │
│  OutlineNode │ Relationship │ ConceptAnatomy         │
├─────────────────────────────────────────────────────┤
│              Core (Config │ Logging │ Exceptions)     │
└─────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **分层架构**：每层只依赖下层，领域模型作为跨层契约
2. **策略模式**：4 种分析策略可独立扩展
3. **聚合器模式**：跨块知识合并（概念去重、重要性提升、关系合并）
4. **渲染器模式**：单一 KnowledgeModel → 6 种产物格式
5. **Provider 统一**：通过 OpenAI SDK 的 base_url 配置统一 4 种 LLM 后端

## 产物示例

拆书完成后，输出目录包含：

```
output/深度工作/
├── manifest.json           # 产物清单
├── knowledge_model.json    # 完整知识模型（可重新渲染）
├── notes.md                # Markdown 笔记
├── notes.org               # Org-mode 笔记
├── mindmap.html            # 思维导图（可交互）
├── concept_cards.html      # 知识卡片
├── infographic.html        # 信息图
└── anatomy_chart.html      # 概念剖析图
```

## 开发

```bash
# 安装开发依赖
make dev

# 运行测试
make test

# 代码检查
make lint

# 格式化
make format

# 类型检查
make type-check
```

### 测试覆盖

- **单元测试**：各层独立测试（Mock LLM）
- **集成测试**：跨格式解析验证
- **系统测试**：端到端渲染、序列化、管道流程
- **API 测试**：FastAPI TestClient 端到端

## 开发状态

- [x] 阶段 1：领域模型与配置基础设施
- [x] 阶段 2：LLM 抽象层（多 provider 统一接入）
- [x] 阶段 3：分析与聚合管线（4 策略 + 聚合器）
- [x] 阶段 4：渲染层基础（Markdown / OrgMode / 思维导图）
- [x] 阶段 5：渲染层进阶 + 导出层（卡片 / 信息图 / PNG / HTML / 打包）
- [x] 阶段 6：应用编排层与 CLI（Runner + Typer 命令行）
- [x] 阶段 7：Web UI 与 API 层（FastAPI + 前端上传 / 预览 / 下载）
- [x] 阶段 8：打磨、Docker 部署、CI/CD、开源化

## License

MIT
