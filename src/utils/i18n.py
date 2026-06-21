"""
国际化/多语言支持模块
支持中英文切换，所有UI文本通过此模块获取
"""
import json
import os
from pathlib import Path
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal


class Translator(QObject):
    """翻译器类"""
    language_changed = Signal(str)  # 语言切换信号

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._current_lang = "zh_CN"
        self._translations = {}
        self._callbacks = []  # 语言变更回调列表
        self._load_translations()

    def _load_translations(self):
        """加载所有翻译文件"""
        translations_dir = Path(__file__).parent.parent.parent / "translations"
        if not translations_dir.exists():
            translations_dir = Path("translations")

        for lang_file in translations_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self._translations[lang_code] = json.load(f)
            except Exception as e:
                print(f"Failed to load translation {lang_file}: {e}")

        # 加载默认语言
        if self._current_lang not in self._translations:
            self._current_lang = "zh_CN"

    @property
    def current_language(self) -> str:
        """获取当前语言"""
        return self._current_lang

    def set_language(self, lang_code: str) -> bool:
        """设置语言"""
        if lang_code not in self._translations:
            return False

        self._current_lang = lang_code
        self.language_changed.emit(lang_code)

        # 调用所有注册的回调
        for callback in self._callbacks:
            try:
                callback(lang_code)
            except Exception:
                pass
        return True

    def get_available_languages(self) -> list:
        """获取可用语言列表"""
        return list(self._translations.keys())

    def register_change_callback(self, callback: Callable):
        """注册语言变更回调"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_change_callback(self, callback: Callable):
        """取消注册语言变更回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def t(self, key: str, default: str = None) -> str | dict:
        """
        获取翻译文本
        Args:
            key: 翻译键，格式如 "menu.file" 或 "settings.api_url"
            default: 默认文本，如果找不到翻译则返回此值
        """
        keys = key.split('.')
        result = self._translations.get(self._current_lang, {})

        try:
            for k in keys:
                result = result[k]
            return result
        except (KeyError, TypeError):
            pass

        # 返回默认值或原始key
        return default if default else key

    def tr(self, key: str) -> str | dict:
        """翻译的便捷方法"""
        return self.t(key)


# 全局翻译器实例
translator = Translator()


def t(key: str, default: str = None) -> str:
    """全局翻译函数"""
    return translator.t(key, default)


def set_language(lang_code: str) -> bool:
    """全局设置语言函数"""
    return translator.set_language(lang_code)


def get_current_language() -> str:
    """获取当前语言"""
    return translator.current_language
