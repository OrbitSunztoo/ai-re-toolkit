"""
工具模块
"""
from .logger import log
from .i18n import translator, t, set_language, get_current_language

__all__ = ['log', 'translator', 't', 'set_language', 'get_current_language']
