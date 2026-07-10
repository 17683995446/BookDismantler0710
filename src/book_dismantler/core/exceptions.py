"""领域异常层次。

所有异常继承自 ``BookDismantlerError``，便于上层统一捕获。
每层定义自己的异常子类，在边界处将底层 IO/第三方异常转换为领域异常。
每个异常携带 ``code`` 用于 API 错误响应，``message`` 用于用户展示。
"""

from __future__ import annotations

from typing import Any


class BookDismantlerError(Exception):
    """所有 book_dismantler 异常的基类。"""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(self, message: str = "", *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        self.details = details or {}


class ConfigError(BookDismantlerError):
    """配置缺失或非法。"""

    code = "CONFIG_ERROR"
    http_status = 500


class ParseError(BookDismantlerError):
    """文档解析失败（格式不支持、文件损坏等）。"""

    code = "PARSE_ERROR"
    http_status = 400


class LLMError(BookDismantlerError):
    """LLM 调用失败（鉴权、超时、限流、响应非法等）。"""

    code = "LLM_ERROR"
    http_status = 502


class AnalysisError(BookDismantlerError):
    """AI 拆书分析阶段失败。"""

    code = "ANALYSIS_ERROR"
    http_status = 500


class RenderError(BookDismantlerError):
    """渲染产物生成失败。"""

    code = "RENDER_ERROR"
    http_status = 500


class ExportError(BookDismantlerError):
    """导出（PNG/打包）失败。"""

    code = "EXPORT_ERROR"
    http_status = 500


class JobCancelledError(BookDismantlerError):
    """任务被用户取消。"""

    code = "JOB_CANCELLED"
    http_status = 200  # 视为正常业务流


class JobNotFoundError(BookDismantlerError):
    """任务不存在。"""

    code = "JOB_NOT_FOUND"
    http_status = 404

    def __init__(self, job_id: str = "") -> None:
        super().__init__(f"任务 {job_id} 不存在" if job_id else "任务不存在")
        self.details = {"job_id": job_id}


class ArtifactNotFoundError(BookDismantlerError):
    """产物文件不存在。"""

    code = "ARTIFACT_NOT_FOUND"
    http_status = 404


class ValidationError(BookDismantlerError):
    """参数校验失败。"""

    code = "VALIDATION_ERROR"
    http_status = 422


class FileUploadError(BookDismantlerError):
    """文件上传失败（格式不支持、超过大小限制等）。"""

    code = "FILE_UPLOAD_ERROR"
    http_status = 400
