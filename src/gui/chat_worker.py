"""
持续聊天工作线程
实现AI Agent循环：执行工具 → 反馈 → 继续执行 → 直至完成
"""
from PySide6.QtCore import QThread, Signal

from src.ai.providers.base import AIMessage


class PersistentChatWorker(QThread):
    """AI 持续执行工作线程 - 最多15步Agent循环"""

    step_completed = Signal(int, str, str)   # 步骤号, 推理, 结果摘要
    all_done = Signal(str, str)              # 最终报告, 完整日志
    log_signal = Signal(str)
    error = Signal(str)

    def __init__(self, scheduler, tool_executor, message: str, context: str = "",
                 file_path: str = "", max_steps: int = 15):
        super().__init__()
        self.scheduler = scheduler
        self.tool_executor = tool_executor
        self.message = message
        self.context = context
        self.file_path = file_path
        self.max_steps = max_steps
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            if not self.scheduler:
                self.error.emit("AI调度器未初始化，请先配置AI")
                return

            messages = [AIMessage("system", self.scheduler.system_prompt)]
            initial_prompt = self.context
            if self.file_path:
                initial_prompt += f"\n\n当前文件: {self.file_path}"
            initial_prompt += (
                f"\n\n用户指令: {self.message}\n\n"
                "请分析并执行操作。每步只返回一个JSON指令。"
                "如果需要继续执行更多步骤，在reasoning中说明计划，系统会自动反馈结果让你继续。"
                "达到最终结论时设置 is_complete 为 true。"
            )
            messages.append(AIMessage("user", initial_prompt))

            full_log = []
            final_report = ""

            for step in range(1, self.max_steps + 1):
                if self._stop:
                    full_log.append("用户中断")
                    break

                self.log_signal.emit(f"=== AI 步骤 {step} ===")

                try:
                    response = self.scheduler.provider.chat(messages)
                    content = response.content
                except Exception as e:
                    full_log.append(f"步骤{step}: AI请求失败 - {e}")
                    self.error.emit(f"AI请求失败: {e}")
                    return

                try:
                    instruction = self.scheduler._parse_ai_response(content)
                except ValueError as e:
                    full_log.append(f"步骤{step}: 解析AI响应失败 - {e}")
                    self.step_completed.emit(step, "解析错误", f"AI返回无效JSON: {str(e)[:100]}")
                    final_report = "分析中断: AI返回无效JSON"
                    break

                action = instruction.get("action", "")
                reasoning = instruction.get("reasoning", "")
                is_complete = instruction.get("is_complete", False)

                self.log_signal.emit(f"动作: {action} | 推理: {reasoning[:80]}")

                if is_complete or action == "report":
                    final_report = instruction.get("message", "分析完成")
                    full_log.append(f"步骤{step}: 完成")
                    self.step_completed.emit(step, reasoning, f"完成: {final_report[:500]}")
                    break

                if action == "ask_user":
                    final_report = instruction.get("message", "需要用户输入")
                    full_log.append(f"步骤{step}: 需要用户输入")
                    self.step_completed.emit(step, reasoning, f"需要用户输入: {final_report}")
                    break

                if action == "execute_tool":
                    tool_name = instruction.get("tool", "")
                    params = instruction.get("params", {})

                    self.log_signal.emit(f"执行工具: {tool_name}")
                    result = self.tool_executor.execute(tool_name, params)

                    success = result.get("success", False)
                    stdout = result.get("stdout", "")[:2000]
                    stderr = result.get("stderr", "")[:500]

                    status = "成功" if success else "失败"
                    result_summary = f"工具 {tool_name} {status}\n{stdout[:400]}"
                    if stderr:
                        result_summary += f"\n错误: {stderr[:200]}"

                    full_log.append(f"步骤{step}: {tool_name} - {status}")
                    self.step_completed.emit(step, reasoning, result_summary)

                    feedback = (
                        f"上一步工具执行结果:\n"
                        f"工具: {tool_name}\n"
                        f"状态: {status}\n"
                        f"输出:\n{stdout}\n\n"
                        "请根据以上结果继续下一步操作，返回新的JSON指令。"
                        "如果分析已完成，设置 is_complete 为 true 并输出最终报告。"
                    )
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                elif action in ("write", "delete", "create"):
                    session = type("Session", (), {
                        "file_path": self.file_path,
                        "tool_outputs": [],
                        "step_count": step
                    })()
                    result = self.scheduler._execute_instruction(instruction, session)
                    status = result.get("status", "unknown")
                    output = result.get("output", "")

                    full_log.append(f"步骤{step}: 文件操作 {action} - {status}")
                    self.step_completed.emit(step, reasoning, f"文件操作({action}): {output[:400]}")

                    feedback = (
                        f"文件操作完成: {output}\n\n"
                        "请继续下一步，或设置 is_complete 为 true 结束。"
                    )
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                elif action == "analyze":
                    full_log.append(f"步骤{step}: 分析")
                    self.step_completed.emit(step, reasoning, "分析中...")
                    feedback = "请继续执行具体工具来完成分析。"
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                else:
                    full_log.append(f"步骤{step}: 未知动作 {action}")
                    self.step_completed.emit(step, reasoning, f"未知动作: {action}")
                    final_report = f"遇到未知动作: {action}"
                    break
            else:
                full_log.append("达到最大步数限制")
                self.step_completed.emit(self.max_steps, "", "达到最大步数限制")
                final_report = "分析达到最大步数限制，可能未完成"

            self.all_done.emit(final_report, "\n".join(full_log))

        except Exception as e:
            self.error.emit(str(e))
