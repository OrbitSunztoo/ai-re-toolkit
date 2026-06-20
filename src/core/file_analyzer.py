"""
文件类型识别模块
通过魔数(Magic Number)和文件结构识别二进制文件类型
"""
import struct
import os
from enum import Enum, auto
from typing import Dict, Optional, Tuple


class FileType(Enum):
    UNKNOWN = auto()
    PE_WINDOWS = auto()      # Windows PE/EXE/DLL
    ELF_LINUX = auto()       # Linux ELF
    MACHO_MAC = auto()       # macOS Mach-O
    APK_ANDROID = auto()     # Android APK
    DEX_ANDROID = auto()     # Android DEX
    JAR_JAVA = auto()        # Java JAR
    JS_PLAIN = auto()        # JavaScript
    JS_OBFUSCATED = auto()   # 混淆JS
    PYTHON_BYTECODE = auto() # Python pyc
    NET_ASSEMBLY = auto()    # .NET Assembly
    ZIP_ARCHIVE = auto()     # ZIP
    RAW_BINARY = auto()      # 原始二进制


class FileAnalyzer:
    """文件分析器：识别文件类型和基本属性"""

    # 魔数映射表
    MAGIC_SIGNATURES: Dict[bytes, FileType] = {
        b'MZ': FileType.PE_WINDOWS,
        b'\x7fELF': FileType.ELF_LINUX,
        b'PK\x03\x04': FileType.ZIP_ARCHIVE,  # APK/JAR/ZIP
        b'PK\x05\x06': FileType.ZIP_ARCHIVE,  # 空ZIP
        b'PK\x07\x08': FileType.ZIP_ARCHIVE,  # ZIP64
        b'dex\x0a': FileType.DEX_ANDROID,
        b'\xca\xfe\xba\xbe': FileType.JAR_JAVA,  # Java class
        b'\xcf\xfa\xed\xfe': FileType.MACHO_MAC,  # Mach-O 64bit
        b'\xfe\xed\xfa\xcf': FileType.MACHO_MAC,  # Mach-O 32bit
    }

    # 需要二次确认的ZIP子类型
    ZIP_SUBTYPES = {
        '.apk': FileType.APK_ANDROID,
        '.jar': FileType.JAR_JAVA,
        '.zip': FileType.ZIP_ARCHIVE,
    }

    @classmethod
    def analyze(cls, file_path: str) -> Dict:
        """
        分析文件，返回完整信息字典
        {
            'path': str,
            'type': FileType,
            'type_name': str,
            'size': int,
            'magic': str,
            'arch': Optional[str],
            'is_packed': bool,
            'suggested_tools': List[str]
        }
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        result = {
            'path': file_path,
            'type': FileType.UNKNOWN,
            'type_name': 'unknown',
            'size': os.path.getsize(file_path),
            'magic': '',
            'arch': None,
            'is_packed': False,
            'suggested_tools': []
        }

        # 读取文件头部
        with open(file_path, 'rb') as f:
            header = f.read(64)

        if not header:
            return result

        result['magic'] = header[:16].hex()

        # 识别基本类型
        file_type = cls._detect_by_magic(header, file_path)
        result['type'] = file_type
        result['type_name'] = file_type.name.lower()

        # 深度解析
        if file_type == FileType.PE_WINDOWS:
            arch, is_packed = cls._parse_pe(header, file_path)
            result['arch'] = arch
            result['is_packed'] = is_packed
            result['suggested_tools'] = ['detect_it_easy', 'upx', 'ghidra', 'strings']

        elif file_type == FileType.ELF_LINUX:
            arch = cls._parse_elf(header)
            result['arch'] = arch
            result['suggested_tools'] = ['readelf', 'objdump', 'radare2', 'strings']

        elif file_type in (FileType.APK_ANDROID, FileType.DEX_ANDROID):
            result['suggested_tools'] = ['jadx', 'apktool', 'dexdump']

        elif file_type == FileType.ZIP_ARCHIVE:
            result['suggested_tools'] = ['unzip', 'strings']

        elif file_type == FileType.JS_PLAIN or file_path.endswith('.js'):
            result['type'] = FileType.JS_PLAIN
            result['type_name'] = 'javascript'
            result['suggested_tools'] = ['js_deobfuscate', 'prettier']

        return result

    @classmethod
    def _detect_by_magic(cls, header: bytes, file_path: str) -> FileType:
        """通过魔数识别文件类型"""
        for magic, ftype in cls.MAGIC_SIGNATURES.items():
            if header.startswith(magic):
                if ftype == FileType.ZIP_ARCHIVE:
                    return cls._classify_zip(file_path)
                return ftype

        # 检查文本文件（JS等）
        try:
            text = header.decode('utf-8', errors='ignore')
            if any(kw in text for kw in ['function', 'var', 'const', 'let', '=>']):
                return FileType.JS_PLAIN
        except:
            pass

        return FileType.UNKNOWN

    @classmethod
    def _classify_zip(cls, file_path: str) -> FileType:
        """分类ZIP文件（APK/JAR/ZIP）"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in cls.ZIP_SUBTYPES:
            return cls.ZIP_SUBTYPES[ext]

        # 检查内部结构
        try:
            import zipfile
            with zipfile.ZipFile(file_path, 'r') as z:
                names = z.namelist()
                if 'AndroidManifest.xml' in names:
                    return FileType.APK_ANDROID
                if 'META-INF/MANIFEST.MF' in names:
                    return FileType.JAR_JAVA
        except:
            pass

        return FileType.ZIP_ARCHIVE

    @classmethod
    def _parse_pe(cls, header: bytes, file_path: str) -> Tuple[Optional[str], bool]:
        """解析PE文件头部信息"""
        try:
            # 从MZ头获取PE头偏移
            pe_offset = struct.unpack_from('<I', header, 0x3C)[0]
            if pe_offset + 4 > len(header):
                with open(file_path, 'rb') as f:
                    f.seek(pe_offset)
                    sig = f.read(4)
            else:
                sig = header[pe_offset:pe_offset+4]

            if sig != b'PE\x00\x00':
                return None, False

            # 机器类型
            with open(file_path, 'rb') as f:
                f.seek(pe_offset + 4)
                machine = struct.unpack('<H', f.read(2))[0]

            arch_map = {
                0x014c: 'x86',
                0x8664: 'x64',
                0x01c0: 'arm',
                0xaa64: 'arm64',
            }
            arch = arch_map.get(machine, f'unknown({hex(machine)})')

            # 简单查壳检测（检查常见UPX特征）
            is_packed = b'UPX' in header[:1024] or b'UPX0' in header[:1024]

            return arch, is_packed
        except struct.error as e:
            # PE头解析错误
            from src.utils.logger import log
            log.warning(f"PE头解析错误: {e}")
            return None, False
        except IOError as e:
            from src.utils.logger import log
            log.warning(f"读取PE文件失败: {e}")
            return None, False
        except Exception as e:
            from src.utils.logger import log
            log.warning(f"PE解析未知错误: {e}")
            return None, False

    @classmethod
    def _parse_elf(cls, header: bytes) -> Optional[str]:
        """解析ELF文件头部信息"""
        try:
            ei_class = header[4]  # 32/64位
            e_machine = struct.unpack_from('<H', header, 18)[0]

            arch_map = {
                0x03: 'x86',
                0x3E: 'x64',
                0x28: 'arm',
                0xB7: 'arm64',
                0xF3: 'riscv',
            }
            arch = arch_map.get(e_machine, f'unknown({hex(e_machine)})')
            bits = '64' if ei_class == 2 else '32'

            return f"{arch}_{bits}"
        except Exception:
            return None


# 便捷函数
def analyze_file(file_path: str) -> Dict:
    """便捷函数：分析单个文件"""
    return FileAnalyzer.analyze(file_path)
