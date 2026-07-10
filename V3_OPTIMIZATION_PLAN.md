# V3 手机端逻辑连贯性优化方案

> 基于视觉模型全流程体验（13张截图、5条流程）发现的 21 个优化点
> 按优先级分 4 个实现阶段（B-E），每阶段前验证前序阶段

## 阶段划分

| 阶段 | 优先级 | 优化项数 | 核心目标 |
|:---:|:---:|:---:|:---|
| B | P0 | 6 | 数据一致性 + 导航连贯性 |
| C | P1 | 7 | 交互细节 + 触摸友好 |
| D | P1 | 4 | 深色模式视觉增强 |
| E | P2 | 4 | 信息密度 + 视觉节奏 |
| F | — | — | 全量回归测试 |

---

## 阶段B：P0 数据一致性与导航连贯性（6项）

| ID | 优化点 | 文件 | 实现方式 |
|:---|:---|:---|:---|
| B1 | 新任务卡片创建后高亮 | app.js createJob | switchTab("jobs") 后传 jobId，loadJobs 完成后为该卡片添加 .job-new-highlight 类，2秒后移除 |
| B2 | 任务页→知识页自动选中对应用任务 | app.js openKnowledgeForJob | 已实现（sel.value = jobId），需验证 refreshKnowledgeJobs 的 option value 是否匹配 job_id |
| B3 | 概念搜索栏 Sticky 全宽度生效 | style.css .km-search-bar | 将 position:sticky 从 460px 媒体查询移到通用规则 |
| B4 | 设置页保存成功反馈动画 | app.js saveSettings | 保存成功后按钮变绿+勾号 1.5秒 |
| B5 | "reconciled" 不显示在元信息 | app.js jobItemHtml | provider 为 "reconciled" 时不 push 标签 |
| B6 | 重复任务区分 + "0.0秒"修正 | app.js jobItemHtml + refreshKnowledgeJobs | 下拉项追加日期；duration=0 显示"示例数据" |

## 阶段C：P1 交互细节与触摸友好（7项）

| ID | 优化点 | 文件 | 实现方式 |
|:---|:---|:---|:---|
| C1 | "查看产物"按钮 min-height 44px 全断点 | style.css .job-actions .btn | 通用规则 min-height:44px |
| C2 | "下载全部ZIP"改按钮样式 | style.css .artifact-toolbar #download-all-btn | 改为 btn-primary 描边样式 |
| C3 | 下载按钮 hover/active 反馈 | style.css .artifact-dl | 添加 :hover/:active 背景填充 |
| C4 | ECharts 节点标签防截断 | index.html label 配置 | 添加 overflow:"truncate", width:80, formatter 截断 |
| C5 | 全屏控制栏首次提示 | app.js 全屏逻辑 | 首次进入全屏显示 toast"轻触屏幕显示控制栏" |
| C6 | 知识页下拉项追加区分标识 | app.js refreshKnowledgeJobs | option 文本追加 " (MM-DD)" 日期 |
| C7 | 任务详情"返回列表"按钮可见性 | style.css .job-detail-back | 移动端 sticky 顶部 |

## 阶段D：P1 深色模式增强（4项）

| ID | 优化点 | 文件 | 实现方式 |
|:---|:---|:---|:---|
| D1 | 分类色标高饱和色板 | style.css dark 模式 | --cat-tech/learning/life 变量提亮 |
| D2 | 书籍卡片背景提亮 | style.css dark .sample-book-card | 背景从透明改为 rgba(255,255,255,0.04) |
| D3 | 上传虚线框用 border-strong | style.css dark .drop-zone | 已有，确认 dashed 使用 strong 变量 |
| D4 | Header 图标进一步提亮 | style.css dark .icon-btn | 颜色从 c8ccd4 提至 d1d5db |

## 阶段E：P2 信息密度与视觉节奏（4项）

| ID | 优化点 | 文件 | 实现方式 |
|:---|:---|:---|:---|
| E1 | 概念卡片定义限2行+示例折叠 | app.js + style.css | 定义 -webkit-line-clamp:2，示例 details 折叠 |
| E2 | 概念卡片添加容器边框 | style.css .km-concept-card | 添加 1px border + 浅色背景 |
| E3 | Hero 描述拆分 bullet | index.html / app.js | 描述拆为 3 个短句分行 |
| E4 | 统计卡片移动端隐藏确认 | style.css .km-summary | 确认 460px 以下 display:none 生效 |

## 阶段F：全量回归测试

- ruff lint
- pytest 单元测试（覆盖率 ≥75%）
- Node 前端模块测试
- 浏览器系统测试（浅色+深色模式关键流程）
