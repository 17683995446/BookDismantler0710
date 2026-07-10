"""应用配置：基于 pydantic-settings 的分层配置。

配置优先级（高 → 低）：
    1. 环境变量（BOOK_DISMANTLER_ 前缀）
    2. .env 文件
    3. 代码内默认值

YAML 配置文件（config/default.yaml）在阶段 6 集成时叠加加载。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置。"""

    model_config = SettingsConfigDict(
        env_prefix="book_dismantler_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM Provider ---
    default_provider: str = "siliconflow"
    default_model: str = "THUDM/GLM-4-9B-0414"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    gemini_api_key: str = ""
    gemini_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    ollama_api_key: str = "ollama"  # Ollama 不需要真实 key，占位即可
    ollama_base_url: str = "http://localhost:11434/v1"

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"

    # --- 处理参数 ---
    chunk_size: int = Field(default=2000, ge=100, le=32000, description="分块目标 token 数")
    chunk_overlap: int = Field(default=200, ge=0, le=2000, description="分块重叠 token 数")
    max_concurrent: int = Field(default=4, ge=1, le=32, description="最大并发 LLM 请求数")
    llm_timeout: int = Field(default=120, ge=10, le=600, description="单次 LLM 请求超时秒数")
    llm_max_retries: int = Field(default=3, ge=0, le=10, description="LLM 最大重试次数")

    # --- 路径 ---
    output_dir: Path = Field(default=Path("./output"), description="产物输出目录")

    # --- 日志 ---
    log_level: str = "INFO"

    @field_validator("output_dir")
    @classmethod
    def ensure_output_dir(cls, v: Path) -> Path:
        """输出目录不存在时自动创建。"""
        v.mkdir(parents=True, exist_ok=True)
        return v

    def get_provider_config(self, provider: str | None = None) -> dict[str, str]:
        """获取指定 provider 的 api_key 与 base_url。

        Args:
            provider: provider 名称，为 None 时使用 default_provider。

        Returns:
            包含 ``api_key``、``base_url``、``model`` 的字典。

        Raises:
            ValueError: provider 未知。
        """
        name = provider or self.default_provider
        prefix = name.lower()
        api_key = getattr(self, f"{prefix}_api_key", "")
        base_url = getattr(self, f"{prefix}_base_url", "")
        if not base_url:
            raise ValueError(f"未知 provider: {name}")
        return {"api_key": api_key, "base_url": base_url, "model": self.default_model}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局 Settings 单例。"""
    return Settings()
