"""
AI 调度核心
实现Agent循环：AI判断→执行工具→反馈→循环直到完成
"""
import json
import os
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

from .providers.base import BaseProvider, AIMessage, AIResponse
from .providers.openai_provider import make_provider, PROVIDER_PRESETS, PROVIDER_MODELS


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
        AI可以自由响应，也可以选择调用工具执行操作
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
            AIMessage("user", self._build_analysis_prompt(file_info))
        ]

        self._notify(f"开始分析: {os.path.basename(file_path)}")
        self._notify(f"文件类型: {file_info.get('type_name', 'unknown')}")

        # AI分析循环 - 支持工具调用（可选）
        import re
        import json
        
        for step in range(1, session.max_steps + 1):
            session.step_count = step
            self._notify(f"--- 步骤 {step} ---")

            try:
                response = self.provider.chat(messages)
                if not response or not response.content:
                    raise ValueError("AI返回了空响应")
                content = response.content
            except Exception as e:
                self._notify(f"AI响应错误: {e}")
                session.final_report = f"分析中断: AI响应错误 - {e}"
                break

            messages.append(AIMessage("assistant", content))

            # 检查是否包含工具调用
            tool_call = None
            pattern = r'```tool_call\s*(\{.*?\})\s*```'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    tool_call = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

            if tool_call:
                action = tool_call.get("action", "")
                tool_name = tool_call.get("tool", "")
                params = tool_call.get("params", {})

                if action == "execute_tool" and tool_name:
                    self._notify(f"执行工具: {tool_name}")
                    result = self._execute_instruction(tool_call, session)
                    success = result.get("status") == "ok"
                    output = result.get("output", "")[:2000]
                    status = "成功" if success else "失败"
                    self._notify(f"工具执行{status}: {output[:300]}")

                    feedback = f"工具执行结果:\n工具: {tool_name}\n状态: {status}\n输出:\n{output}\n\n请根据结果继续分析或总结。"
                    messages.append(AIMessage("user", feedback))
                    messages = self.provider.truncate_history(messages)
                    continue

                elif action in ("write", "delete", "create"):
                    result = self._execute_instruction(tool_call, session)
                    self._notify(f"文件操作({action}): {result.get('output', '')[:200]}")
                    feedback = f"文件操作完成: {result.get('output', '')}\n\n请继续分析。"
                    messages.append(AIMessage("user", feedback))
                    messages = self.provider.truncate_history(messages)
                    continue

            # 没有工具调用，认为分析完成
            session.is_complete = True
            session.final_report = content
            self._notify("分析完成")
            break

        if session.step_count >= session.max_steps:
            session.final_report = f"分析达到最大步数限制\n\n最后结果:\n{content}"
            self._notify(session.final_report)

        return session

    def _build_analysis_prompt(self, file_info: Dict) -> str:
        """构建初始分析提示"""
        return f"""请分析以下文件，给出详细的分析报告。

文件信息:
- 路径: {file_info.get('path', '')}
- 类型: {file_info.get('type_name', 'unknown')}
- 大小: {file_info.get('size', 0)} bytes
- 架构: {file_info.get('arch', 'unknown')}
- 是否加壳: {'是' if file_info.get('is_packed', False) else '否'}
- 建议工具: {', '.join(file_info.get('suggested_tools', []))}

你可以直接分析并给出结论，也可以调用工具获取更多信息。请给出完整的分析报告。
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
    """Provider 工厂类 - 统一入口"""

    @classmethod
    def create(cls, name: str, config: Dict) -> BaseProvider:
        """创建Provider实例"""
        return make_provider(name, config)

    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有可用Provider"""
        return list(PROVIDER_PRESETS.keys())

    @classmethod
    def get_models(cls, provider_name: str) -> List[str]:
        """获取指定Provider的模型列表"""
        return PROVIDER_MODELS.get(provider_name, [])

    @classmethod
    def get_all_models(cls) -> Dict[str, List[str]]:
        """获取所有Provider的模型映射"""
        return PROVIDER_MODELS.copy()
