"""
DashScope Error Parsers
=======================

Modular error parsing for Alibaba Cloud DashScope API errors.
"""

from ._utils import has_chinese_characters
from ._400_errors import parse_400_errors
from ._401_403_errors import parse_401_errors, parse_403_errors
from ._404_errors import parse_404_errors
from ._429_errors import parse_429_errors
from ._500_503_errors import parse_500_errors, parse_503_errors
from ._content_filter_errors import parse_content_filter_errors
from ._specialized_errors import parse_specialized_errors

__all__ = [
    'has_chinese_characters',
    'parse_400_errors',
    'parse_401_errors',
    'parse_403_errors',
    'parse_404_errors',
    'parse_429_errors',
    'parse_500_errors',
    'parse_503_errors',
    'parse_content_filter_errors',
    'parse_specialized_errors',
]
