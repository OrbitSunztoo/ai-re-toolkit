"""
工具执行器
安全地调用外部命令行工具，捕获输出和错误
"""
import subprocess
import os
import tempfile
import hashlib
from typing import Dict, Optional, List
from pathlib import Path

from .registry import ToolRegistry


class ToolExecutor:
    """
    工具执行器
    封装子进程调用，提供统一的执行接口
    """

    def __init__(self, registry: Optional[ToolRegistry] = None,
                 timeout: int = 300, max_output: int = 1048576):
        self.registry = registry or ToolRegistry()
        self.default_timeout = timeout
        self.max_output_size = max_output
        self._cache_dir = "./cache/tool_outputs"
        os.makedirs(self._cache_dir, exist_ok=True)

    def execute(self, tool_name: str, params: Dict,
                timeout: Optional[int] = None,
                use_cache: bool = True) -> Dict:
        """
        执行指定工具
        Args:
            tool_name: 工具名称
            params: 参数字典
            timeout: 超时秒数
            use_cache: 是否使用缓存
        Returns:
            {
                "success": bool,
                "stdout": str,
                "stderr": str,
                "returncode": int,
                "cached": bool,
                "duration": float
            }
        """
        import time
        start_time = time.time()

        # 0. 检查是否是 Python 原生工具
        python_result = self._execute_python_tool(tool_name, params, use_cache)
        if python_result is not None:
            python_result["duration"] = time.time() - start_time
            return python_result

        # 1. 验证工具
        valid, msg = self.registry.validate_tool(tool_name)
        if not valid:
            return {
                "success": False,
                "stdout": "",
                "stderr": msg,
                "returncode": -1,
                "cached": False,
                "duration": 0
            }

        # 2. 检查缓存
        if use_cache:
            cache_key = self._make_cache_key(tool_name, params)
            cached = self._get_cache(cache_key)
            if cached:
                cached["cached"] = True
                cached["duration"] = 0
                return cached

        # 3. 构建命令
        try:
            cmd = self.registry.get_command(tool_name, params)
            if not cmd:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "无法构建命令",
                    "returncode": -1,
                    "cached": False,
                    "duration": 0
                }
        except ValueError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "cached": False,
                "duration": 0
            }

        # 4. 执行命令
        tool_info = self.registry.get_tool(tool_name)
        tool_timeout = timeout or (tool_info.get("timeout") if tool_info else None) or self.default_timeout

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=tool_timeout,
                encoding='utf-8',
                errors='replace'
            )

            stdout = result.stdout[:self.max_output_size]
            stderr = result.stderr[:self.max_output_size // 4]

            output = {
                "success": result.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": result.returncode,
                "cached": False,
                "duration": time.time() - start_time
            }

            # 5. 保存缓存
            if use_cache:
                self._set_cache(cache_key, output)

            return output

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"执行超时 ({tool_timeout}秒)",
                "returncode": -1,
                "cached": False,
                "duration": time.time() - start_time
            }
        except FileNotFoundError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"可执行文件未找到: {e}",
                "returncode": -1,
                "cached": False,
                "duration": time.time() - start_time
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"执行异常: {e}",
                "returncode": -1,
                "cached": False,
                "duration": time.time() - start_time
            }

    def execute_pipeline(self, steps: List[Dict]) -> List[Dict]:
        """
        执行工具链（多个工具按顺序执行）
        steps: [{"tool": str, "params": dict}, ...]
        """
        results = []
        for step in steps:
            result = self.execute(step["tool"], step.get("params", {}))
            results.append({
                "tool": step["tool"],
                "result": result
            })
            # 如果某一步失败，中断流水线
            if not result["success"] and step.get("required", True):
                break
        return results

    def _make_cache_key(self, tool_name: str, params: Dict) -> str:
        """生成缓存键"""
        data = f"{tool_name}:{sorted(params.items())}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _get_cache(self, cache_key: str) -> Optional[Dict]:
        """读取缓存"""
        cache_file = os.path.join(self._cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            import json
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
        return None

    def _set_cache(self, cache_key: str, output: Dict):
        """写入缓存"""
        cache_file = os.path.join(self._cache_dir, f"{cache_key}.json")
        import json
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    def clear_cache(self):
        """清除所有缓存"""
        import glob
        for f in glob.glob(os.path.join(self._cache_dir, "*.json")):
            os.remove(f)

    # Python 原生工具注册表
    _PYTHON_TOOLS = {
        "pefile_analyze": {
            "func": lambda params: ToolExecutor._run_pefile_static(params.get("file", "")),
            "description": "PE文件分析"
        },
        "apk_analyze": {
            "func": lambda params: ToolExecutor._run_apk_static(params.get("file", "")),
            "description": "APK分析"
        },
        "file_info": {
            "func": lambda params: ToolExecutor._run_file_info_static(params.get("file", "")),
            "description": "综合文件分析"
        },
        "ipa_analyze": {
            "func": lambda params: ToolExecutor._run_ipa_static(params.get("file", "")),
            "description": "IPA分析"
        },
        "jadx_decompile": {
            "func": lambda params: ToolExecutor._run_jadx_static(params.get("file", ""), params.get("output_dir", "")),
            "description": "JADX反编译APK"
        },
        "apktool_disassemble": {
            "func": lambda params: ToolExecutor._run_apktool_static(params.get("file", ""), params.get("output_dir", "")),
            "description": "APKTool拆包"
        },
        "apktool_rebuild": {
            "func": lambda params: ToolExecutor._run_apktool_rebuild(params.get("input_dir", ""), params.get("output_apk", "")),
            "description": "APKTool重打包"
        },
        "read_file": {
            "func": lambda params: ToolExecutor._read_file_content(params.get("file_path", "")),
            "description": "读取文件内容"
        },
        "list_directory": {
            "func": lambda params: ToolExecutor._list_directory(params.get("dir_path", "")),
            "description": "列出目录内容"
        }
    }

    def _execute_python_tool(self, tool_name: str, params: Dict, use_cache: bool) -> Optional[Dict]:
        """执行 Python 原生工具"""
        if tool_name not in self._PYTHON_TOOLS:
            return None  # 不是 Python 工具，继续常规流程

        tool_info = self._PYTHON_TOOLS[tool_name]

        # 检查缓存
        if use_cache:
            cache_key = self._make_cache_key(tool_name, params)
            cached = self._get_cache(cache_key)
            if cached:
                cached["cached"] = True
                cached["duration"] = 0
                return cached

        # 执行工具
        try:
            result = tool_info["func"](params)
            output = {
                "success": result.get("success", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "returncode": 0 if result.get("success") else 1,
                "cached": False
            }

            # 保存缓存
            if use_cache:
                cache_key = self._make_cache_key(tool_name, params)
                self._set_cache(cache_key, output)

            return output

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "cached": False
            }

    @staticmethod
    def _run_pefile_static(file_path: str) -> Dict:
        """运行 pefile 分析"""
        from .python_tools import PEPETool, HAS_PEFILE

        if not HAS_PEFILE:
            return {
                "success": False,
                "stdout": "",
                "stderr": "pefile库未安装，请运行: pip install pefile"
            }

        result = PEPETool.analyze(file_path)
        formatted = ToolExecutor._format_pe_result(result)
        return {
            "success": result.get("success", False),
            "stdout": formatted,
            "stderr": result.get("error", "")
        }

    @staticmethod
    def _run_apk_static(file_path: str) -> Dict:
        """运行 APK 分析"""
        from .python_tools import APKTool, HAS_APK

        if not HAS_APK:
            return {
                "success": False,
                "stdout": "",
                "stderr": "pyaxmlparser库未安装，请运行: pip install pyaxmlparser"
            }

        result = APKTool.analyze(file_path)
        formatted = ToolExecutor._format_apk_result(result)
        return {
            "success": result.get("success", False),
            "stdout": formatted,
            "stderr": result.get("error", "")
        }

    @staticmethod
    def _run_file_info_static(file_path: str) -> Dict:
        """运行综合文件分析"""
        from .python_tools import FileInfoTool

        result = FileInfoTool.analyze(file_path)
        formatted = ToolExecutor._format_file_info(result)
        return {
            "success": result.get("success", False),
            "stdout": formatted,
            "stderr": ""
        }

    @staticmethod
    def _run_ipa_static(file_path: str) -> Dict:
        """运行 IPA 分析"""
        result = ToolExecutor._analyze_ipa(file_path)
        formatted = ToolExecutor._format_ipa_result(result)
        return {
            "success": result.get("success", False),
            "stdout": formatted,
            "stderr": result.get("error", "")
        }

    @staticmethod
    def _analyze_ipa(file_path: str) -> Dict:
        """分析 IPA 文件"""
        import zipfile
        import plistlib
        import os

        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}

        result = {
            "success": True,
            "files": [],
            "info_plist": {},
            "embedded_binaries": []
        }

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # 列出所有文件
                result["files"] = zf.namelist()

                # 解析 Info.plist
                info_plist_path = None
                for name in zf.namelist():
                    if name.endswith('Info.plist'):
                        info_plist_path = name
                        break

                if info_plist_path:
                    with zf.open(info_plist_path) as pf:
                        result["info_plist"] = plistlib.load(pf)

                # 查找二进制文件
                for name in zf.namelist():
                    if '/Frameworks/' in name and name.endswith('.framework'):
                        result["embedded_binaries"].append(name)
                    elif name.endswith('.app'):
                        result["embedded_binaries"].append(name)

        except zipfile.BadZipFile:
            return {"success": False, "error": "无效的 IPA 文件（非 ZIP 格式）"}
        except Exception as e:
            return {"success": False, "error": str(e)}

        return result

    @staticmethod
    def _run_jadx_static(file_path: str, output_dir: str) -> Dict:
        """使用 JADX 反编译 APK"""
        from .registry import ToolRegistry
        import os

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(file_path), "jadx_output")

        os.makedirs(output_dir, exist_ok=True)

        registry = ToolRegistry()
        valid, msg = registry.validate_tool("jadx")
        if not valid:
            return {"success": False, "stderr": f"JADX未安装: {msg}"}

        cmd = registry.get_command("jadx", {"file": file_path, "output_dir": output_dir})
        if not cmd:
            return {"success": False, "stderr": "无法构建JADX命令"}

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                encoding='utf-8', errors='replace'
            )
            return {
                "success": result.returncode == 0,
                "stdout": f"反编译输出: {output_dir}\n{result.stdout[:2000]}",
                "stderr": result.stderr[:500]
            }
        except Exception as e:
            return {"success": False, "stderr": str(e)}

    @staticmethod
    def _run_apktool_static(file_path: str, output_dir: str) -> Dict:
        """使用 APKTool 拆包"""
        from .registry import ToolRegistry
        import os

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(file_path), "apktool_output")

        os.makedirs(output_dir, exist_ok=True)

        registry = ToolRegistry()
        valid, msg = registry.validate_tool("apktool")
        if not valid:
            return {"success": False, "stderr": f"APKTool未安装: {msg}"}

        cmd = registry.get_command("apktool", {"file": file_path, "output_dir": output_dir})
        if not cmd:
            return {"success": False, "stderr": "无法构建APKTool命令"}

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                encoding='utf-8', errors='replace'
            )
            return {
                "success": result.returncode == 0,
                "stdout": f"拆包输出: {output_dir}\n{result.stdout[:2000]}",
                "stderr": result.stderr[:500]
            }
        except Exception as e:
            return {"success": False, "stderr": str(e)}

    @staticmethod
    def _run_apktool_rebuild(input_dir: str, output_apk: str) -> Dict:
        """使用 APKTool 重打包"""
        from .registry import ToolRegistry
        import os

        if not output_apk:
            output_apk = input_dir + "_rebuilt.apk"

        registry = ToolRegistry()
        valid, msg = registry.validate_tool("apktool")
        if not valid:
            return {"success": False, "stderr": f"APKTool未安装: {msg}"}

        # 构建重打包命令
        executable = registry.get_executable("apktool")
        if not executable:
            return {"success": False, "stderr": "无法找到apktool可执行文件"}

        cmd = [executable, "b", input_dir, "-o", output_apk]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                encoding='utf-8', errors='replace'
            )
            return {
                "success": result.returncode == 0 and os.path.exists(output_apk),
                "stdout": f"重打包完成: {output_apk}",
                "stderr": result.stderr[:500]
            }
        except Exception as e:
            return {"success": False, "stderr": str(e)}

    @staticmethod
    def _read_file_content(file_path: str) -> Dict:
        """读取文件内容"""
        import os

        if not os.path.exists(file_path):
            return {"success": False, "stderr": f"文件不存在: {file_path}"}

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(50000)  # 限制读取大小
            return {
                "success": True,
                "stdout": content,
                "stderr": ""
            }
        except Exception as e:
            return {"success": False, "stderr": str(e)}

    @staticmethod
    def _list_directory(dir_path: str) -> Dict:
        """列出目录内容"""
        import os

        if not os.path.exists(dir_path):
            return {"success": False, "stderr": f"目录不存在: {dir_path}"}

        try:
            items = os.listdir(dir_path)
            lines = [f"{'[DIR]' if os.path.isdir(os.path.join(dir_path, i)) else '[FILE]'} {i}" for i in items]
            return {
                "success": True,
                "stdout": "\n".join(lines),
                "stderr": ""
            }
        except Exception as e:
            return {"success": False, "stderr": str(e)}

    @staticmethod
    def _format_pe_result(result: Dict) -> str:
        """格式化 PE 分析结果"""
        if not result.get("success"):
            return f"分析失败: {result.get('error', '未知错误')}"

        lines = ["=" * 50,
                 "PE 文件分析结果",
                 "=" * 50,
                 f"架构: {result.get('arch', 'unknown')}",
                 f"机器类型: {result.get('machine_name', 'Unknown')}"]

        if result.get("characteristics"):
            lines.append(f"特性: {', '.join(result['characteristics'])}")

        lines.extend(["", "--- 节表 ---"])
        for sec in result.get("sections", []):
            lines.append(f"  {sec['name']}: VSize={sec['virtual_size']}, RawSize={sec['raw_size']}")

        lines.extend(["", "--- 导入表 ---"])
        for imp in result.get("imports", []):
            lines.append(f"  [{imp['dll']}]")
            for func in imp.get("functions", [])[:5]:
                lines.append(f"    - {func}")
            if len(imp.get("functions", [])) > 5:
                lines.append(f"    ... (+{len(imp['functions']) - 5} more)")

        if result.get("exports"):
            lines.extend(["", "--- 导出表 ---"])
            for exp in result["exports"][:20]:
                lines.append(f"  - {exp}")

        return "\n".join(lines)

    @staticmethod
    def _format_apk_result(result: Dict) -> str:
        """格式化 APK 分析结果"""
        if not result.get("success"):
            return f"分析失败: {result.get('error', '未知错误')}"

        lines = ["=" * 50,
                 "APK 文件分析结果",
                 "=" * 50,
                 f"包名: {result.get('package', 'unknown')}",
                 f"版本: {result.get('version', 'unknown')} ({result.get('version_code', 'N/A')})",
                 f"最低SDK: {result.get('min_sdk', 'N/A')}",
                 f"目标SDK: {result.get('target_sdk', 'N/A')}"]

        if result.get("permissions"):
            lines.extend(["", f"--- 权限 ({len(result['permissions'])}) ---"])
            for perm in result["permissions"][:15]:
                lines.append(f"  - {perm}")
            if len(result["permissions"]) > 15:
                lines.append(f"  ... (+{len(result['permissions']) - 15} more)")

        if result.get("activities"):
            lines.extend(["", f"--- Activity ({len(result['activities'])}) ---"])
            for act in result["activities"][:10]:
                lines.append(f"  - {act}")

        if result.get("native_libs"):
            lines.extend(["", f"--- Native库 ({len(result['native_libs'])}) ---"])
            for lib in result["native_libs"][:10]:
                lines.append(f"  - {lib}")

        return "\n".join(lines)

    @staticmethod
    def _format_file_info(result: Dict) -> str:
        """格式化综合文件分析结果"""
        if not result.get("success"):
            return "分析失败"

        lines = ["=" * 50,
                 "综合文件分析",
                 "=" * 50]

        basic = result.get("basic", {})
        lines.extend([
            f"文件类型: {basic.get('type_name', 'unknown')}",
            f"大小: {basic.get('size', 0)} bytes",
            f"架构: {basic.get('arch', 'N/A')}",
            f"加壳: {'是' if basic.get('is_packed') else '否'}"
        ])

        details = result.get("details", {})
        if details.get("success") or details.get("stdout"):
            lines.extend(["", "--- 详细信息 ---"])
            lines.append(details.get("stdout", ""))

        return "\n".join(lines)

    @staticmethod
    def _format_ipa_result(result: Dict) -> str:
        """格式化 IPA 分析结果"""
        if not result.get("success"):
            return f"分析失败: {result.get('error', '未知错误')}"

        lines = ["=" * 50,
                 "iOS IPA 文件分析结果",
                 "=" * 50]

        info = result.get("info_plist", {})
        lines.extend([
            f"Bundle ID: {info.get('CFBundleIdentifier', 'N/A')}",
            f"应用名称: {info.get('CFBundleName', 'N/A')}",
            f"版本: {info.get('CFBundleShortVersionString', 'N/A')} ({info.get('CFBundleVersion', 'N/A')})",
            f"最低iOS版本: {info.get('MinimumOSVersion', 'N/A')}",
            f"设备支持: {', '.join(info.get('UIDeviceFamily', ['Unknown']))}"
        ])

        # URL Schemes
        if info.get('CFBundleURLTypes'):
            lines.extend(["", "--- URL Schemes ---"])
            for url in info['CFBundleURLTypes']:
                schemes = url.get('CFBundleURLSchemes', [])
                lines.append(f"  - {', '.join(schemes)}")

        # Capabilities
        if info.get('UIBackgroundModes'):
            lines.extend(["", "--- 后台模式 ---"])
            for mode in info['UIBackgroundModes']:
                lines.append(f"  - {mode}")

        # 嵌入式框架
        embedded = result.get("embedded_binaries", [])
        if embedded:
            lines.extend(["", f"--- 嵌入式内容 ({len(embedded)}) ---"])
            for item in embedded[:20]:
                lines.append(f"  - {item}")
            if len(embedded) > 20:
                lines.append(f"  ... (+{len(embedded) - 20} more)")

        lines.extend(["", f"--- 总文件数: {len(result.get('files', []))} ---"])

        return "\n".join(lines)
