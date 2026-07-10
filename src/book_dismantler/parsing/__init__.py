"""解析层：将原始电子书转换为统一 ``ParsedDocument``。"""

from book_dismantler.parsing.base import Parser
from book_dismantler.parsing.registry import get_parser_for_file

__all__ = ["Parser", "get_parser_for_file"]
