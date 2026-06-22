"""
聊天工作线程
支持AI自由响应，同时可选调用工具执行操作
"""
import json
import re
from PySide6.QtCore import QThread, Signal

from src.ai.providers.base import AIMessage
from src.utils.i18n import t


class ChatWorker(QThread):
    """
    聊天工作线程
    AI可以自由响应，也可以选择调用工具执行操作
    """

    response_ready = Signal(str)
    tool_executed = Signal(str, str)
    log_signal = Signal(str)
    error = Signal(str)

    def __init__(self, scheduler, tool_executor, message: str, context: str = "",
                 file_path: str = "", max_tool_rounds: int = 5):
        super().__init__()
        self.scheduler = scheduler
        self.tool_executor = tool_executor
        self.message = message
        self.context = context
        self.file_path = file_path
        self.max_tool_rounds = max_tool_rounds
        self._stop = False

    def stop(self):
        self._stop = True

    def _extract_tool_call(self, content: str):
        """从AI响应中提取tool_call块"""
        pattern = r'```tool_call\s*(\{.*?\})\s*```'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _execute_tool(self, tool_name: str, params: dict):
        """执行工具"""
        if not self.tool_executor:
            return {"success": False, "stdout": "", "stderr": "工具执行器未注册"}

        try:
            result = self.tool_executor.execute(tool_name, params)
            return result
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    def run(self):
        try:
            if not self.scheduler:
                self.error.emit(t("worker.ai_not_init"))
                return

            messages = [AIMessage("system", self.scheduler.system_prompt)]

            full_prompt = ""
            if self.context:
                full_prompt += self.context + "\n\n"

            if self.file_path:
                w = t("worker")
                full_prompt += f"{w['current_file']}: {self.file_path}\n\n"

            full_prompt += f"{t('worker.user_command')}: {self.message}"
            messages.append(AIMessage("user", full_prompt))

            self.log_signal.emit(f"[Chat] {t('messages.ai_processing')}...")

            if self._stop:
                return

            tool_round = 0
            while tool_round < self.max_tool_rounds:
                if self._stop:
                    return

                try:
                    response = self.scheduler.provider.chat(messages)
                    content = response.content
                except Exception as e:
                    self.error.emit(f"{t('worker.ai_request_failed')}: {e}")
                    return

                messages.append(AIMessage("assistant", content))

                tool_call = self._extract_tool_call(content)

                if tool_call:
                    action = tool_call.get("action", "")
                    tool_name = tool_call.get("tool", "")
                    params = tool_call.get("params", {})
                    reasoning = tool_call.get("reasoning", "")

                    if action == "execute_tool" and tool_name:
                        self.log_signal.emit(f"[Chat] {t('messages.tool_execution')}: {tool_name}")

                        result = self._execute_tool(tool_name, params)
                        success = result.get("success", False)
                        stdout = result.get("stdout", "")[:2000]
                        stderr = result.get("stderr", "")[:500]

                        status = t("messages.tool_success") if success else t("messages.tool_failed")
                        result_summary = f"{status}\n{stdout[:500]}"
                        if stderr:
                            result_summary += f"\nError: {stderr[:200]}"

                        self.tool_executed.emit(reasoning, result_summary)

                        feedback = f"工具执行结果:\n工具: {tool_name}\n状态: {status}\n输出:\n{stdout}\n\n请根据结果继续分析或总结。"
                        messages.append(AIMessage("user", feedback))
                        messages = self.scheduler.provider.truncate_history(messages)

                        tool_round += 1
                        continue

                    elif action in ("write", "delete", "create"):
                        result = self.scheduler._execute_instruction(tool_call, None)
                        status = result.get("status", "unknown")
                        output = result.get("output", "")

                        self.tool_executed.emit(reasoning, f"文件操作({action}): {output[:400]}")

                        feedback = f"文件操作完成: {output}\n\n请根据结果继续。"
                        messages.append(AIMessage("user", feedback))
                        messages = self.scheduler.provider.truncate_history(messages)

                        tool_round += 1
                        continue

                break

            self.log_signal.emit(f"[Chat] {t('messages.chat_completed')}")
            self.response_ready.emit(content)

        except Exception as e:
            self.error.emit(str(e))
