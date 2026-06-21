"""
Python 原生逆向工具
封装 pefile、pyaxmlparser 等库，提供跨平台逆向分析能力
"""
import os
import json
from pathlib import Path
from typing import Dict, Optional, List
import zipfile

# 可选导入，失败时提供 fallback
try:
    import pefile
    HAS_PEFILE = True
except ImportError:
    HAS_PEFILE = False

try:
    from pyaxmlparser import APK
    HAS_APK = True
except ImportError:
    HAS_APK = False


class PEPETool:
    """PE文件分析工具（pefile封装）"""

    @staticmethod
    def analyze(file_path: str) -> Dict:
        """
        分析PE文件，返回详细信息
        """
        if not HAS_PEFILE:
            return {
                "success": False,
                "error": "pefile库未安装，请运行: pip install pefile"
            }

        try:
            pe = pefile.PE(file_path)

            result = {
                "success": True,
                "type": "PE",
                "machine": pe.FILE_HEADER.Machine,
                "machine_name": pefile.MACHINE_TYPE.get(pe.FILE_HEADER.Machine, "Unknown"),
                "timestamp": pe.FILE_HEADER.TimeDateStamp,
                "sections": [],
                "imports": [],
                "exports": [],
                "resources": [],
            }

            # 机器类型
            machine_map = {
                0x014c: "x86",
                0x8664: "x64",
                0x01c0: "ARM",
                0xaa64: "ARM64",
            }
            result["arch"] = machine_map.get(pe.FILE_HEADER.Machine, "unknown")

            # 节表
            for section in pe.sections:
                result["sections"].append({
                    "name": section.Name.decode('utf-8', errors='ignore').strip('\x00'),
                    "virtual_size": section.Misc_VirtualSize,
                    "raw_size": section.SizeOfRawData,
                    "characteristics": section.Characteristics,
                })

            # 导入表
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    dll_name = entry.dll.decode('utf-8', errors='ignore')
                    funcs = []
                    for imp in entry.imports:
                        if imp.name:
                            funcs.append(imp.name.decode('utf-8', errors='ignore'))
                    result["imports"].append({
                        "dll": dll_name,
                        "functions": funcs[:20]  # 限制数量
                    })

            # 导出表
            if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
                for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                    if exp.name:
                        result["exports"].append(exp.name.decode('utf-8', errors='ignore'))

            # 特性检测
            result["characteristics"] = []
            flags = [
                (pe.FILE_HEADER.IMAGE_FILE_RELOCS_STRIPPED, "RELOCS_STRIPPED"),
                (pe.FILE_HEADER.IMAGE_FILE_EXECUTABLE_IMAGE, "EXECUTABLE"),
                (pe.FILE_HEADER.IMAGE_FILE_DLL, "DLL"),
                (pe.FILE_HEADER.IMAGE_FILE_LARGE_ADDRESS_AWARE, "LARGE_ADDRESS_AWARE"),
            ]
            for flag, name in flags:
                if flag:
                    result["characteristics"].append(name)

            pe.close()
            return result

        except Exception as e:
            from src.utils.logger import log
            log.error(f"PE文件分析失败 [{file_path}]: {e}")
            return {
                "success": False,
                "error": f"分析失败 [{os.path.basename(file_path)}]: {str(e)}"
            }

    @staticmethod
    def get_strings(file_path: str, min_length: int = 4) -> List[str]:
        """提取PE文件中的字符串"""
        from src.core.binary_reader import BinaryReader
        reader = BinaryReader(file_path)
        strings_data = reader.extract_strings(min_length=min_length)
        return [s[1] for s in strings_data[:500]]  # 限制数量


class APKTool:
    """APK文件分析工具（pyaxmlparser封装）"""

    @staticmethod
    def analyze(file_path: str) -> Dict:
        """
        分析APK文件，返回详细信息
        """
        if not HAS_APK:
            return {
                "success": False,
                "error": "pyaxmlparser库未安装，请运行: pip install pyaxmlparser"
            }

        try:
            apk = APK(file_path)

            result = {
                "success": True,
                "type": "APK",
                "package": apk.package,
                "version": apk.version,
                "version_code": apk.version_code,
                "min_sdk": apk.min_sdk,
                "target_sdk": apk.sdk,
                "permissions": apk.permissions,
                "activities": [],
                "services": [],
                "receivers": [],
                "providers": [],
            }

            # 组件
            if hasattr(apk, 'activities') and apk.activities:
                result["activities"] = [a.split('.')[-1] for a in apk.activities]

            if hasattr(apk, 'services') and apk.services:
                result["services"] = [s.split('.')[-1] for s in apk.services]

            if hasattr(apk, 'receivers') and apk.receivers:
                result["receivers"] = [r.split('.')[-1] for r in apk.receivers]

            # 提取文件列表
            result["file_count"] = 0
            result["dex_files"] = []
            result["native_libs"] = []

            try:
                with zipfile.ZipFile(file_path, 'r') as zf:
                    for name in zf.namelist():
                        result["file_count"] += 1
                        if name.endswith('.dex'):
                            result["dex_files"].append(name)
                        elif name.endswith('.so'):
                            result["native_libs"].append(name.split('/')[-1])
            except zipfile.BadZipFile:
                return {"success": False, "error": "无效的APK文件（非ZIP格式）"}
            except Exception as e:
                from src.utils.logger import log
                log.error(f"APK文件分析失败 [{file_path}]: {e}")
                return {
                    "success": False,
                    "error": f"分析失败 [{os.path.basename(file_path)}]: {str(e)}"
                }

            return result

        except Exception as e:
            from src.utils.logger import log
            log.error(f"APK分析异常 [{file_path}]: {e}")
            return {"success": False, "error": f"分析失败: {str(e)}"}


class FileInfoTool:
    """通用文件信息工具"""

    @staticmethod
    def analyze(file_path: str) -> Dict:
        """
        综合分析文件，返回尽可能多的信息
        """
        from src.core.file_analyzer import FileAnalyzer, FileType

        # 先用原生分析器
        basic_info = FileAnalyzer.analyze(file_path)

        result = {
            "success": True,
            "basic": basic_info,
            "details": {}
        }

        # 根据类型添加详细信息
        file_type = basic_info.get("type")

        if file_type == FileType.PE_WINDOWS and HAS_PEFILE:
            result["details"] = PEPETool.analyze(file_path)

        elif file_type in (FileType.APK_ANDROID, FileType.DEX_ANDROID) and HAS_APK:
            result["details"] = APKTool.analyze(file_path)

        elif file_type == FileType.ZIP_ARCHIVE:
            result["details"] = FileInfoTool._analyze_zip(file_path)

        return result

    @staticmethod
    def _analyze_zip(file_path: str) -> Dict:
        """分析ZIP文件"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                names = zf.namelist()
                return {
                    "success": True,
                    "type": "ZIP",
                    "file_count": len(names),
                    "files": names[:100]  # 限制数量
                }
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_python_tools(registry):
    """注册Python原生工具到工具注册表"""
    # 这些是Python实现的内置工具
    python_tools = {
        "pefile_analyze": {
            "name": "pefile_analyze",
            "display_name": "PE文件分析 (Python)",
            "description": "使用pefile库分析PE文件结构",
            "type": "python",
            "function": "pefile",
            "params": [{"name": "file", "type": "path", "required": True}]
        },
        "apk_analyze": {
            "name": "apk_analyze",
            "display_name": "APK分析 (Python)",
            "description": "使用pyaxmlparser分析APK结构",
            "type": "python",
            "function": "apk",
            "params": [{"name": "file", "type": "path", "required": True}]
        },
        "file_info": {
            "name": "file_info",
            "display_name": "综合文件分析",
            "description": "综合分析文件类型和结构",
            "type": "python",
            "function": "file_info",
            "params": [{"name": "file", "type": "path", "required": True}]
        }
    }
    return python_tools
