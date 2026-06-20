"""
二进制文件读取工具
提供安全的二进制文件读取、字符串提取、十六进制查看功能
"""
import struct
import re
from typing import List, Tuple, Optional, Iterator


class BinaryReader:
    """安全二进制文件读取器"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._size = None
        self._cached_data = None

    @property
    def size(self) -> int:
        """获取文件大小"""
        if self._size is None:
            import os
            self._size = os.path.getsize(self.file_path)
        return self._size

    def read_bytes(self, offset: int = 0, length: int = 1024) -> bytes:
        """读取指定范围的二进制数据"""
        with open(self.file_path, 'rb') as f:
            f.seek(offset)
            return f.read(length)

    def read_struct(self, offset: int, fmt: str) -> Tuple:
        """按结构体格式读取数据"""
        size = struct.calcsize(fmt)
        data = self.read_bytes(offset, size)
        if len(data) < size:
            raise ValueError(f"数据不足: 需要{size}字节, 实际{len(data)}字节")
        return struct.unpack(fmt, data)

    def iter_blocks(self, block_size: int = 4096) -> Iterator[bytes]:
        """分块读取文件，适合大文件"""
        with open(self.file_path, 'rb') as f:
            while True:
                chunk = f.read(block_size)
                if not chunk:
                    break
                yield chunk

    def extract_strings(self, min_length: int = 4, encoding: str = 'utf-8',
                       scan_all: bool = False) -> List[Tuple[int, str]]:
        """
        从二进制中提取可打印字符串
        返回: [(offset, string), ...]
        """
        strings = []
        pattern = re.compile(b'[\x20-\x7e]{' + str(min_length).encode() + b',}')

        if scan_all:
            # 扫描整个文件
            with open(self.file_path, 'rb') as f:
                data = f.read()
        else:
            # 只扫描前1MB（加速）
            data = self.read_bytes(0, 1024 * 1024)

        for match in pattern.finditer(data):
            try:
                text = match.group().decode(encoding)
                strings.append((match.start(), text))
            except UnicodeDecodeError:
                continue

        return strings

    def extract_strings_wide(self, min_length: int = 2) -> List[Tuple[int, str]]:
        """
        提取UTF-16LE宽字符字符串（Windows常用）
        """
        strings = []
        pattern = re.compile(b'(?:[\x20-\x7e]\x00){' + str(min_length).encode() + b',}')

        data = self.read_bytes(0, 1024 * 1024)

        for match in pattern.finditer(data):
            try:
                text = match.group().decode('utf-16le')
                strings.append((match.start(), text))
            except UnicodeDecodeError:
                continue

        return strings

    def hex_dump(self, offset: int = 0, length: int = 256,
                 bytes_per_line: int = 16) -> str:
        """
        生成十六进制查看文本
        """
        data = self.read_bytes(offset, length)
        lines = []

        for i in range(0, len(data), bytes_per_line):
            chunk = data[i:i + bytes_per_line]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            hex_part = hex_part.ljust(bytes_per_line * 3 - 1)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{offset + i:08x}  {hex_part}  |{ascii_part}|')

        return '\n'.join(lines)

    def find_pattern(self, pattern: bytes, start: int = 0) -> List[int]:
        """搜索字节模式，返回所有匹配偏移"""
        offsets = []
        with open(self.file_path, 'rb') as f:
            f.seek(start)
            data = f.read()

        idx = data.find(pattern)
        while idx != -1:
            offsets.append(start + idx)
            idx = data.find(pattern, idx + 1)

        return offsets

    def get_entropy(self, block_size: int = 256) -> float:
        """
        计算文件熵值（检测加密/压缩）
        0-8之间，>7通常表示加密或压缩
        """
        import math
        data = self.read_bytes(0, min(block_size * 4, self.size))

        if not data:
            return 0.0

        entropy = 0
        for x in range(256):
            p = data.count(bytes([x])) / len(data)
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy


class StringExtractor:
    """字符串提取器（支持多种编码和过滤）"""

    def __init__(self, file_path: str):
        self.reader = BinaryReader(file_path)

    def extract_all(self, min_length: int = 4,
                   include_wide: bool = True) -> List[Tuple[int, str, str]]:
        """
        提取所有类型的字符串
        返回: [(offset, string, encoding), ...]
        """
        results = []

        # ASCII/UTF-8
        for offset, s in self.reader.extract_strings(min_length, 'utf-8'):
            results.append((offset, s, 'utf-8'))

        # UTF-16LE
        if include_wide:
            for offset, s in self.reader.extract_strings_wide(min_length):
                results.append((offset, s, 'utf-16le'))

        # 去重并排序
        seen = set()
        unique = []
        for item in sorted(results, key=lambda x: x[0]):
            key = (item[1], item[2])
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique
