"""
工具注册表
管理所有逆向工具的元数据和配置
"""
import json
import os
import glob
from typing import Dict, List, Optional, Any


class ToolRegistry:
    """
    工具注册表：加载、查询和管理工具配置
    所有工具定义存储在 JSON 文件中，新增工具只需添加配置
    """

    def __init__(self, definitions_dir: Optional[str] = None):
        self.tools: Dict[str, Dict] = {}
        self.categories: Dict[str, Dict] = {}
        self.definitions_dir = definitions_dir or self._default_definitions_dir()
        self._load_all_definitions()

    def _default_definitions_dir(self) -> str:
        """默认工具定义目录"""
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "definitions")

    def _load_all_definitions(self):
        """加载所有工具定义JSON文件"""
        pattern = os.path.join(self.definitions_dir, "*.json")
        for filepath in glob.glob(pattern):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    definition = json.load(f)
                category = definition.get("category", "unknown")
                self.categories[category] = {
                    "description": definition.get("description", ""),
                    "tools": []
                }
                for tool in definition.get("tools", []):
                    tool["category"] = category
                    self.tools[tool["name"]] = tool
                    self.categories[category]["tools"].append(tool["name"])
            except Exception as e:
                print(f"[警告] 加载工具定义失败 {filepath}: {e}")

    def get_tool(self, name: str) -> Optional[Dict]:
        """获取工具配置"""
        return self.tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """列出所有工具名称"""
        if category:
            return self.categories.get(category, {}).get("tools", [])
        return list(self.tools.keys())

    def list_categories(self) -> List[str]:
        """列出所有工具类别"""
        return list(self.categories.keys())

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具的友好信息"""
        tool = self.tools.get(name)
        if not tool:
            return None
        return {
            "name": tool["name"],
            "display_name": tool.get("display_name", tool["name"]),
            "description": tool.get("description", ""),
            "category": tool.get("category", "unknown"),
            "timeout": tool.get("timeout", 60),
            "params": tool.get("params", [])
        }

    def get_executable(self, name: str, platform: Optional[str] = None) -> Optional[str]:
        """
        获取工具在当前平台的可执行文件路径
        Args:
            name: 工具名称
            platform: 指定平台 ('windows', 'linux', None则自动检测)
        """
        tool = self.tools.get(name)
        if not tool:
            return None

        if platform is None:
            import sys
            platform = "windows" if sys.platform == "win32" else "linux"

        executables = tool.get("executable", {})
        exe = executables.get(platform)

        # 如果是系统命令（如readelf），直接返回
        if exe and not os.path.sep in exe:
            return exe

        # 相对路径转绝对路径（相对于项目根目录）
        if exe:
            base_dir = self._get_project_root()
            abs_path = os.path.join(base_dir, exe)
            if os.path.exists(abs_path):
                return abs_path
            # 如果未打包，检查是否安装了系统版本
            return exe

        return None

    def get_command(self, name: str, params: Dict, platform: Optional[str] = None) -> Optional[List[str]]:
        """
        构建命令行参数列表
        Returns:
            [executable, arg1, arg2, ...] 或 None
        """
        tool = self.tools.get(name)
        if not tool:
            return None

        executable = self.get_executable(name, platform)
        if not executable:
            return None

        template = tool.get("command_template", "{executable} {file}")

        # 构建参数字典，包含所有可能的参数
        format_dict = {"executable": executable}
        for param_def in tool.get("params", []):
            param_name = param_def["name"]
            if param_name in params:
                format_dict[param_name] = params[param_name]
            elif "default" in param_def:
                format_dict[param_name] = param_def["default"]
            elif param_def.get("required", False):
                raise ValueError(f"工具 {name} 缺少必需参数: {param_name}")
            else:
                format_dict[param_name] = ""

        # 安全格式化：使用安全的替换方式
        cmd_str = template
        for key, value in format_dict.items():
            # 转义特殊字符防止命令注入
            safe_value = str(value).replace('"', '\\"').replace('`', '\\`')
            cmd_str = cmd_str.replace(f"{{{key}}}", safe_value)

        # 移除模板中未被替换的占位符
        import re
        cmd_str = re.sub(r'\{[^}]+\}', '', cmd_str)
        # 清理多余空格
        cmd_str = ' '.join(cmd_str.split())

        if not cmd_str.strip():
            return [executable]

        # 分割为参数列表
        import shlex
        try:
            return shlex.split(cmd_str)
        except ValueError:
            return cmd_str.split()

    def _get_project_root(self) -> str:
        """获取项目根目录"""
        current = os.path.dirname(os.path.abspath(__file__))
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, "src")):
                return current
            current = os.path.dirname(current)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def validate_tool(self, name: str) -> tuple[bool, str]:
        """
        验证工具是否可用
        Returns: (是否可用, 错误信息)
        """
        tool = self.tools.get(name)
        if not tool:
            return False, f"未知工具: {name}"

        exe = self.get_executable(name)
        if not exe:
            return False, f"工具 {name} 在当前平台没有可用可执行文件"

        # 检查文件是否存在（非系统命令）
        if os.path.sep in exe and not os.path.exists(exe):
            return False, f"可执行文件不存在: {exe}"

        return True, "OK"

    def find_tools_for_filetype(self, file_type: str) -> List[str]:
        """
        根据文件类型查找推荐工具
        """
        mapping = {
            "pe_windows": ["detect_it_easy", "upx", "ghidra_analyze", "strings"],
            "elf_linux": ["readelf", "objdump", "radare2", "strings"],
            "apk_android": ["jadx", "apktool", "dexdump"],
            "javascript": ["js_deobfuscate", "prettier"],
        }
        return mapping.get(file_type.lower(), ["strings"])
