"""提示词加载与渲染。

从 config/prompts/ 加载 Jinja2 模板，渲染为最终提示词。
与代码分离，便于迭代提示词而无需改代码。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from book_dismantler.core.exceptions import ConfigError
from book_dismantler.core.logging import get_logger

logger = get_logger("analysis.prompts")

# 提示词目录（相对于项目根）
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts"

# 单例 Environment
_env: Environment | None = None


def _get_env() -> Environment:
    """获取 Jinja2 Environment 单例。"""
    global _env
    if _env is None:
        if not _PROMPTS_DIR.exists():
            logger.warning("提示词目录不存在: %s", _PROMPTS_DIR)
        _env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
    return _env


def render_prompt(template_name: str, **variables: Any) -> str:
    """渲染提示词模板。

    Args:
        template_name: 模板文件名（如 ``outline_extraction.j2``）。
        **variables: 模板变量。

    Returns:
        渲染后的提示词字符串。

    Raises:
        ConfigError: 模板不存在或渲染失败。
    """
    env = _get_env()
    try:
        template = env.get_template(template_name)
    except Exception as e:
        raise ConfigError(f"加载提示词模板 '{template_name}' 失败: {e}") from e

    try:
        return template.render(**variables)
    except Exception as e:
        raise ConfigError(f"渲染提示词模板 '{template_name}' 失败: {e}") from e


def list_templates() -> list[str]:
    """列出所有可用提示词模板。"""
    if not _PROMPTS_DIR.exists():
        return []
    return sorted(
        f.name for f in _PROMPTS_DIR.glob("*.j2") if f.is_file()
    )
