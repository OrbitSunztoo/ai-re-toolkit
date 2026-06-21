"""
持续聊天工作线程
实现AI Agent循环：执行工具 → 反馈 → 继续执行 → 直至完成
"""
from PySide6.QtCore import QThread, Signal

from src.ai.providers.base import AIMessage
from src.utils.i18n import t


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
                self.error.emit(t("worker.ai_not_init"))
                return

            messages = [AIMessage("system", self.scheduler.system_prompt)]
            w = t("worker")

            initial_prompt = self.context
            if self.file_path:
                initial_prompt += f"\n\n{w['current_file']}: {self.file_path}"
            initial_prompt += (
                f"\n\n{w['user_command']}: {self.message}\n\n"
                f"{w['analyze_instruction']}"
                f"{w['continue_instruction']}"
                f"{w['complete_instruction']}"
            )
            messages.append(AIMessage("user", initial_prompt))

            full_log = []
            final_report = ""

            for step in range(1, self.max_steps + 1):
                if self._stop:
                    full_log.append(t("messages.user_interrupt"))
                    break

                self.log_signal.emit(f"=== {t('messages.ai_step')} {step} ===")

                try:
                    response = self.scheduler.provider.chat(messages)
                    content = response.content
                except Exception as e:
                    full_log.append(f"Step{step}: {w['ai_request_failed']} - {e}")
                    self.error.emit(f"{w['ai_request_failed']}: {e}")
                    return

                try:
                    instruction = self.scheduler._parse_ai_response(content)
                except ValueError as e:
                    full_log.append(f"Step{step}: {w['parse_failed']} - {e}")
                    self.step_completed.emit(step, "Parse Error", f"{w['invalid_json']}: {str(e)[:100]}")
                    final_report = w['analysis_interrupted'] + ": " + w['invalid_json']
                    break

                action = instruction.get("action", "")
                reasoning = instruction.get("reasoning", "")
                is_complete = instruction.get("is_complete", False)

                self.log_signal.emit(f"Action: {action} | {reasoning[:80]}")

                if is_complete or action == "report":
                    final_report = instruction.get("message", t("messages.analysis_complete"))
                    full_log.append(f"Step{step}: {w['completed']}")
                    self.step_completed.emit(step, reasoning, f"{w['completed']}: {final_report[:500]}")
                    break

                if action == "ask_user":
                    final_report = instruction.get("message", t("messages.user_input_required"))
                    full_log.append(f"Step{step}: {t('messages.user_input_required')}")
                    self.step_completed.emit(step, reasoning, f"{t('messages.user_input_required')}: {final_report}")
                    break

                if action == "execute_tool":
                    tool_name = instruction.get("tool", "")
                    params = instruction.get("params", {})

                    self.log_signal.emit(f"{w['tool_execution']}: {tool_name}")
                    result = self.tool_executor.execute(tool_name, params)

                    success = result.get("success", False)
                    stdout = result.get("stdout", "")[:2000]
                    stderr = result.get("stderr", "")[:500]

                    status = t("messages.tool_success") if success else t("messages.tool_failed")
                    result_summary = f"{w['tool_name']} {tool_name} {status}\n{stdout[:400]}"
                    if stderr:
                        result_summary += f"\nError: {stderr[:200]}"

                    full_log.append(f"Step{step}: {tool_name} - {status}")
                    self.step_completed.emit(step, reasoning, result_summary)

                    feedback = (
                        f"{w['tool_result']}:\n"
                        f"{w['tool_name']}: {tool_name}\n"
                        f"{w['status']}: {status}\n"
                        f"{w['output']}:\n{stdout}\n\n"
                        f"{w['continue_result']}"
                        f"{w['continue_or_finish']}"
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
                    status = result.get("status", w["unknown"])
                    output = result.get("output", "")

                    full_log.append(f"Step{step}: {w['file_operation']} {action} - {status}")
                    self.step_completed.emit(step, reasoning, f"{w['file_operation']}({action}): {output[:400]}")

                    feedback = (
                        f"{w['file_operation_complete']}: {output}\n\n"
                        f"{t('messages.continue_or_complete')}"
                    )
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                elif action == "analyze":
                    full_log.append(f"Step{step}: {t('messages.analyzing_in_progress').replace('...', '')}")
                    self.step_completed.emit(step, reasoning, t("messages.analyzing_in_progress"))
                    feedback = w['continue_operation']
                    messages.append(AIMessage("assistant", content))
                    messages.append(AIMessage("user", feedback))
                    messages = self.scheduler.provider.truncate_history(messages)

                else:
                    full_log.append(f"Step{step}: {t('messages.unknown_action')} {action}")
                    self.step_completed.emit(step, reasoning, f"{t('messages.unknown_action')}: {action}")
                    final_report = f"{t('messages.unknown_action')}: {action}"
                    break
            else:
                full_log.append(t("messages.max_steps_reached"))
                self.step_completed.emit(self.max_steps, "", t("messages.max_steps_reached"))
                final_report = t("messages.analysis_incomplete")

            self.all_done.emit(final_report, "\n".join(full_log))

        except Exception as e:
            self.error.emit(str(e))
