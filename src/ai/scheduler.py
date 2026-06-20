"""
AI 调度核心
实现Agent循环：AI判断→执行工具→反馈→循环直到完成
"""
import json
import os
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

from .providers.base import BaseProvider, AIMessage, AIResponse
from .providers.ollama_provider import OllamaProvider
from .providers.openai_provider import OpenAIProvider, AnthropicProvider
from .providers.other_providers import QwenProvider, KimiProvider, DeepSeekProvider, GrokProvider


@dataclass
class AnalysisSession:
    """分析会话状态"""
    file_path: str
    file_info: Dict = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    tool_outputs: List[Dict] = field(default_factory=list)
    final_report: str = ""
    is_complete: bool = False
    step_count: int = 0
    max_steps: int = 20


class AIScheduler:
    """
    AI 智能调度器
    协调 AI 和工具之间的交互，实现自动化分析流程
    """

    def __init__(self, provider: BaseProvider, prompt_path: Optional[str] = None):
        self.provider = provider
        self.prompt_path = prompt_path or self._default_prompt_path()
        self.system_prompt = self._load_system_prompt()
        self.tool_executor: Optional[Callable] = None
        self.progress_callback: Optional[Callable[[str], None]] = None

    def _default_prompt_path(self) -> str:
        """默认系统提示词路径"""
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "prompts", "system_v1.txt")

    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "You are a reverse engineering assistant. Respond in JSON format only."

    def register_tool_executor(self, executor: Callable[[str, Dict], Dict]):
        """
        注册工具执行器
        executor 签名: (tool_name: str, params: Dict) -> Dict
        """
        self.tool_executor = executor

    def register_progress_callback(self, callback: Callable[[str], None]):
        """注册进度回调函数"""
        self.progress_callback = callback

    def _notify(self, message: str):
        """发送进度通知"""
        if self.progress_callback:
            self.progress_callback(message)

    def _parse_ai_response(self, content: str) -> Dict:
        """
        解析AI返回的JSON指令
        处理可能的格式问题（markdown代码块、多余空白等）
        """
        # 清理可能的markdown代码块
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # 尝试修复常见JSON错误
            try:
                # 查找JSON开始和结束位置
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1:
                    return json.loads(content[start:end+1])
            except:
                pass
            raise ValueError(f"AI返回了无效的JSON: {e}\n内容: {content[:500]}")

    def _validate_instruction(self, instruction: Dict) -> bool:
        """验证AI指令是否合法"""
        required_fields = ["action"]
        for field in required_fields:
            if field not in instruction:
                return False

        valid_actions = ["analyze", "execute_tool", "report", "ask_user", "pack", "write", "delete", "create"]
        if instruction["action"] not in valid_actions:
            return False

        if instruction["action"] == "execute_tool":
            if "tool" not in instruction or not instruction["tool"]:
                return False
            if "params" not in instruction:
                return False

        return True

    def start_analysis(self, file_path: str, file_info: Dict) -> AnalysisSession:
        """
        启动自动化分析流程
        Returns:
            AnalysisSession: 完整的分析会话结果
        """
        session = AnalysisSession(
            file_path=file_path,
            file_info=file_info,
            max_steps=20
        )

        # 构建初始消息
        messages = [
            AIMessage("system", self.system_prompt),
            AIMessage("user", self._build_initial_prompt(file_info))
        ]

        self._notify(f"开始分析: {os.path.basename(file_path)}")
        self._notify(f"文件类型: {file_info.get('type_name', 'unknown')}")

        # Agent 主循环
        while session.step_count < session.max_steps and not session.is_complete:
            session.step_count += 1
            self._notify(f"--- 步骤 {session.step_count} ---")

            # 1. 调用AI获取下一步指令
            try:
                response = self.provider.chat(messages)
                if not response or not response.content:
                    raise ValueError("AI返回了空响应")
                instruction = self._parse_ai_response(response.content)
            except Exception as e:
                self._notify(f"AI响应错误: {e}")
                session.final_report = f"分析中断: AI响应错误 - {e}"
                break

            # 记录历史
            session.history.append({
                "step": session.step_count,
                "ai_instruction": instruction,
                "raw_response": response.content
            })

            # 2. 执行AI指令
            result = self._execute_instruction(instruction, session)

            if instruction.get("is_complete"):
                session.is_complete = True
                session.final_report = instruction.get("message", "分析完成")
                self._notify("分析完成")
                break

            if instruction["action"] == "ask_user":
                session.final_report = instruction.get("message", "需要用户输入")
                self._notify(f"需要用户输入: {session.final_report}")
                break

            # 3. 将结果反馈给AI
            feedback = self._build_feedback(result, session)
            messages.append(AIMessage("assistant", response.content))
            messages.append(AIMessage("user", feedback))

            # 截断历史防止超出token限制
            messages = self.provider.truncate_history(messages)

        if session.step_count >= session.max_steps:
            session.final_report = "分析达到最大步数限制，可能未完成"
            self._notify(session.final_report)

        return session

    def _build_initial_prompt(self, file_info: Dict) -> str:
        """构建初始分析提示"""
        return f"""分析以下二进制文件，请返回下一步操作指令（JSON格式）。

文件信息:
- 路径: {file_info.get('path', '')}
- 类型: {file_info.get('type_name', 'unknown')}
- 大小: {file_info.get('size', 0)} bytes
- 架构: {file_info.get('arch', 'unknown')}
- 是否加壳: {file_info.get('is_packed', False)}
- 建议工具: {', '.join(file_info.get('suggested_tools', []))}

支持平台:
- Windows: EXE, DLL (使用 pefile, DIE, UPX, Ghidra)
- Android: APK, DEX (使用 jadx, apktool, pyaxmlparser)
- iOS: IPA (使用 strings, unzip)

请根据文件类型选择合适的分析流程，返回第一个指令。
"""

    def _execute_instruction(self, instruction: Dict, session: AnalysisSession) -> Dict:
        """执行AI指令"""
        action = instruction.get("action")

        if action == "analyze":
            return {
                "status": "ok",
                "output": f"文件已分析: {session.file_info.get('type_name')}"
            }

        elif action == "execute_tool":
            tool_name = instruction.get("tool", "")
            params = instruction.get("params", {})

            self._notify(f"执行工具: {tool_name}")
            self._notify(f"参数: {json.dumps(params, ensure_ascii=False)}")

            if not self.tool_executor:
                return {
                    "status": "error",
                    "output": "工具执行器未注册"
                }

            try:
                result = self.tool_executor(tool_name, params)
                session.tool_outputs.append({
                    "tool": tool_name,
                    "params": params,
                    "result": result
                })

                output = result.get("stdout", "")[:5000]  # 截断过长输出
                self._notify(f"工具输出长度: {len(output)} chars")

                return {
                    "status": "ok",
                    "output": output,
                    "stderr": result.get("stderr", "")[:1000],
                    "returncode": result.get("returncode", 0)
                }
            except Exception as e:
                error_msg = f"工具执行失败: {e}"
                self._notify(error_msg)
                return {
                    "status": "error",
                    "output": error_msg
                }

        elif action == "pack":
            # 打包/重建功能
            tool_name = instruction.get("tool", "")
            params = instruction.get("params", {})
            message = instruction.get("message", "")

            self._notify(f"打包指令: {tool_name}")
            self._notify(message)

            return {
                "status": "ok",
                "output": f"打包指导:\n{message}",
                "action": "pack"
            }

        elif action == "write":
            # 文件写入操作
            file_path = instruction.get("file_path", "")
            content = instruction.get("content", "")

            self._notify(f"写入文件: {file_path}")

            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                result_msg = f"文件已写入: {file_path}"
                self._notify(result_msg)
                return {"status": "ok", "output": result_msg}
            except Exception as e:
                error_msg = f"写入失败: {e}"
                self._notify(error_msg)
                return {"status": "error", "output": error_msg}

        elif action == "delete":
            # 文件删除操作 - 添加安全校验
            file_path = instruction.get("file_path", "")
            self._notify(f"删除文件: {file_path}")

            # 安全检查
            forbidden = ['\\Windows', '\\Program Files', '/etc/', '/bin/', '/sbin/', '/usr/']
            for forbid in forbidden:
                if forbid.lower() in os.path.abspath(file_path).lower():
                    error_msg = f"禁止删除系统目录: {file_path}"
                    self._notify(error_msg)
                    return {"status": "error", "output": error_msg}

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    result_msg = f"文件已删除: {file_path}"
                else:
                    result_msg = f"文件不存在: {file_path}"
                self._notify(result_msg)
                return {"status": "ok", "output": result_msg}
            except Exception as e:
                error_msg = f"删除失败: {e}"
                self._notify(error_msg)
                return {"status": "error", "output": error_msg}

        elif action == "create":
            # 目录创建操作
            dir_path = instruction.get("dir_path", "")
            self._notify(f"创建目录: {dir_path}")

            try:
                import os
                os.makedirs(dir_path, exist_ok=True)
                result_msg = f"目录已创建: {dir_path}"
                self._notify(result_msg)
                return {"status": "ok", "output": result_msg}
            except Exception as e:
                error_msg = f"创建目录失败: {e}"
                self._notify(error_msg)
                return {"status": "error", "output": error_msg}

        elif action == "report":
            report = instruction.get("message", "")
            session.final_report = report
            return {
                "status": "ok",
                "output": report
            }

        return {"status": "unknown_action", "output": f"未知动作: {action}"}

    def _build_feedback(self, result: Dict, session: AnalysisSession) -> str:
        """构建反馈消息给AI"""
        status = result.get("status", "unknown")
        output = result.get("output", "")

        feedback = f"""上一步执行结果:
- 状态: {status}
- 输出:\n```\n{output}\n```

请根据以上结果返回下一步指令（JSON格式）。如果分析已完成，设置is_complete为true并输出最终报告。
"""
        return feedback

    def quick_chat(self, message: str, context: Optional[str] = None) -> str:
        """
        快速对话（非分析模式）
        用于用户直接询问AI问题
        """
        messages = [AIMessage("system", self.system_prompt)]
        if context:
            messages.append(AIMessage("user", f"上下文:\n{context}\n\n问题: {message}"))
        else:
            messages.append(AIMessage("user", message))

        try:
            response = self.provider.chat(messages)
            return response.content
        except Exception as e:
            return f"[错误] {e}"


class ProviderFactory:
    """Provider 工厂类"""

    _providers = {
        # 本地离线模型
        "ollama": OllamaProvider,
        # OpenAI 系列
        "openai": OpenAIProvider,
        # Anthropic 系列
        "anthropic": AnthropicProvider,
        # 其他云端模型
        "qwen": QwenProvider,      # 通义千问
        "kimi": KimiProvider,      # Kimi (Moonshot)
        "deepseek": DeepSeekProvider,  # DeepSeek
        "grok": GrokProvider,      # Grok (xAI)
        # 自定义（兼容OpenAI格式）
        "custom": OpenAIProvider,
    }

    # 模型映射（Provider名称 -> 模型列表）
    _model_lists = {
        "ollama": ["llama3", "llama3.2", "llama3.2-vision", "codellama", "qwen2.5", "qwen2.5-coder", "mistral", "mixtral", "phi3", "deepseek-coder", "gemma2"],
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1-preview", "o1-mini"],
        "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229"],
        "qwen": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long", "qwen-coder-plus"],
        "kimi": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "deepseek": ["deepseek-chat", "deepseek-coder"],
        "grok": ["grok-2", "grok-2-mini", "grok-beta"],
    }

    @classmethod
    def create(cls, name: str, config: Dict) -> BaseProvider:
        """创建Provider实例"""
        if name not in cls._providers:
            raise ValueError(f"未知的Provider: {name}。可用: {list(cls._providers.keys())}")
        return cls._providers[name](config)

    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有可用Provider"""
        return list(cls._providers.keys())

    @classmethod
    def get_models(cls, provider_name: str) -> List[str]:
        """获取指定Provider的模型列表"""
        return cls._model_lists.get(provider_name, [])

    @classmethod
    def get_all_models(cls) -> Dict[str, List[str]]:
        """获取所有Provider的模型映射"""
        return cls._model_lists.copy()
