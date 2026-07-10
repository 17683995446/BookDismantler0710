"""端到端拆书执行器。

编排完整流程：解析 → 分析 → 渲染 → 导出 → 打包。
这是首个"集成"里程碑：无需 UI 即可完成"电子书 → 全套知识产物"。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from book_dismantler.analysis.pipeline import AnalysisPipeline
from book_dismantler.analysis.strategies import AnalysisStrategy
from book_dismantler.analysis.strategies.anatomy import AnatomyStrategy
from book_dismantler.analysis.strategies.concepts import ConceptStrategy
from book_dismantler.analysis.strategies.outline import OutlineStrategy
from book_dismantler.analysis.strategies.relationships import RelationshipStrategy
from book_dismantler.core.config import Settings, get_settings
from book_dismantler.core.exceptions import BookDismantlerError, JobCancelledError
from book_dismantler.core.logging import get_logger, setup_logging
from book_dismantler.domain.document import ParsedDocument
from book_dismantler.domain.knowledge import KnowledgeModel
from book_dismantler.export.bundler import ArtifactBundler
from book_dismantler.llm.base import LLMClient
from book_dismantler.llm.factory import create_client
from book_dismantler.rendering.anatomy.anatomy_renderer import AnatomyChartRenderer
from book_dismantler.rendering.base import RenderedArtifact
from book_dismantler.rendering.cards.card_renderer import ConceptCardRenderer
from book_dismantler.rendering.graph.graph_renderer import KnowledgeGraphRenderer
from book_dismantler.rendering.infographic.poster import InfographicRenderer
from book_dismantler.rendering.mindmap.markmap import MarkmapRenderer
from book_dismantler.rendering.notes.markdown import MarkdownRenderer
from book_dismantler.rendering.notes.orgmode import OrgModeRenderer

logger = get_logger("application.runner")


class DismantleResult(BaseModel):
    """拆书执行结果。"""

    book_title: str = ""
    knowledge_model: KnowledgeModel | None = None
    artifacts: list[RenderedArtifact] = Field(default_factory=list)
    output_dir: str = ""

    model_config = {"arbitrary_types_allowed": True}


class DismantleRunner:
    """端到端拆书执行器。

    编排解析→分析→渲染→导出→打包全流程。
    """

    def __init__(
        self,
        client: LLMClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client

    def _get_client(self) -> LLMClient:
        """获取 LLM 客户端（懒初始化）。"""
        if self.client is None:
            self.client = create_client(settings=self.settings)
        return self.client

    def _get_strategies(self, book_title: str) -> list[AnalysisStrategy]:
        """构建分析策略列表。"""
        client = self._get_client()
        return [
            OutlineStrategy(client, book_title=book_title),
            ConceptStrategy(client, book_title=book_title),
            RelationshipStrategy(client, book_title=book_title),
            AnatomyStrategy(client, book_title=book_title),
        ]

    def run(
        self,
        book_path: str | Path,
        *,
        output_dir: str | Path | None = None,
        on_progress: Any = None,
        strategies: list[str] | None = None,
        cancel_check: Any = None,
    ) -> DismantleResult:
        """执行完整拆书流程。

        Args:
            book_path: 电子书文件路径。
            output_dir: 输出目录（为 None 时使用 settings.output_dir）。
            on_progress: 进度回调 ``fn(progress: int, step: str)``。
            strategies: 指定策略子集（为 None 时全部执行）。
            cancel_check: 取消检查函数 ``fn() -> bool``，返回 True 时中止。

        Returns:
            拆书结果。

        Raises:
            BookDismantlerError: 流程失败。
        """
        def _check_cancel() -> None:
            if cancel_check and cancel_check():
                raise JobCancelledError("任务已取消")

        def _progress(p: int, step: str = "") -> None:
            if on_progress:
                on_progress(p, step)

        book_path = Path(book_path)
        if not book_path.exists():
            raise BookDismantlerError(f"文件不存在: {book_path}")

        setup_logging(self.settings.log_level)
        logger.info("开始拆书: %s", book_path.name)

        # 1. 解析
        _progress(10, "正在解析文档...")
        logger.info("阶段 1/4: 解析文档...")
        document = ParsedDocument.from_file(book_path)
        book_title = document.metadata.title or book_path.stem
        # 过滤无效标题
        if book_title in ("(anonymous)", "None", ""):
            book_title = book_path.stem
        logger.info(
            "解析完成: %d 章, %d 段落, %d 字符",
            document.chapter_count,
            document.total_paragraphs,
            document.total_chars,
        )

        _check_cancel()

        # 2. 分析
        _progress(20, "AI 分析中（提取大纲/概念/关系）...")
        logger.info("阶段 2/4: AI 分析...")
        all_strategies = self._get_strategies(book_title)
        if strategies:
            all_strategies = [s for s in all_strategies if s.name in strategies]

        pipeline = AnalysisPipeline(
            client=self._get_client(),
            strategies=all_strategies,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            max_concurrent=self.settings.max_concurrent,
        )

        def _pipeline_progress(completed: int, total: int, _idx: int = 0) -> None:
            pct = 20 + int(50 * completed / max(total, 1))
            _progress(pct, f"AI 分析中... ({completed}/{total} 块)")

        knowledge_model = pipeline.run(
            document,
            on_progress=_pipeline_progress,
            cancel_check=cancel_check,
        )
        knowledge_model.book_title = book_title
        knowledge_model.book_author = document.metadata.author or ""

        _check_cancel()

        # 3. 渲染
        _progress(75, "渲染知识产物中...")
        logger.info("阶段 3/4: 渲染产物...")
        artifacts = self._render_all(knowledge_model)
        logger.info("渲染完成: %d 个产物", len(artifacts))

        _check_cancel()

        # 4. 导出打包
        _progress(90, "打包导出中...")
        logger.info("阶段 4/4: 导出打包...")
        out_dir = Path(output_dir) if output_dir else self.settings.output_dir
        out_dir = out_dir / book_title
        bundler = ArtifactBundler()
        bundle_path = bundler.bundle(artifacts, knowledge_model, out_dir)
        logger.info("打包完成: %s", bundle_path)

        _progress(100, "完成")

        return DismantleResult(
            book_title=book_title,
            knowledge_model=knowledge_model,
            artifacts=artifacts,
            output_dir=str(bundle_path),
        )

    def _render_all(self, model: KnowledgeModel) -> list[RenderedArtifact]:
        """渲染所有产物类型。"""
        renderers = [
            MarkdownRenderer(),
            OrgModeRenderer(),
            MarkmapRenderer(),
            ConceptCardRenderer(),
            InfographicRenderer(),
            AnatomyChartRenderer(),
            KnowledgeGraphRenderer(),
        ]

        artifacts: list[RenderedArtifact] = []
        for renderer in renderers:
            try:
                artifact = renderer.render(model)
                artifacts.append(artifact)
            except Exception as e:
                logger.warning("渲染器 %s 失败: %s", renderer.__class__.__name__, e)

        return artifacts

    def parse_only(self, book_path: str | Path) -> ParsedDocument:
        """仅执行解析步骤（分步调试用）。"""
        return ParsedDocument.from_file(book_path)

    def analyze_only(
        self, document: ParsedDocument, book_title: str = ""
    ) -> KnowledgeModel:
        """仅执行分析步骤。"""
        title = book_title or document.metadata.title
        strategies = self._get_strategies(title)
        pipeline = AnalysisPipeline(
            client=self._get_client(),
            strategies=strategies,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        return pipeline.run(document)

    def render_only(self, model: KnowledgeModel) -> list[RenderedArtifact]:
        """仅执行渲染步骤。"""
        return self._render_all(model)
