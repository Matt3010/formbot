import os
import uuid
import asyncio
import logging
from datetime import UTC, datetime
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from app.config import settings
from app.services.stealth import apply_stealth
from app.services.vnc_manager import VNCManager
from app.services.broadcaster import Broadcaster
from app.services.screenshot_storage import ScreenshotStorage
from app.models.task import Task
from app.models.form_definition import FormDefinition
from app.models.form_field import FormField
from app.models.execution_log import ExecutionLog
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class TaskExecutor:
    def __init__(self, db: Session, vnc_manager: VNCManager | None = None):
        self.db = db
        self.vnc_manager = vnc_manager or VNCManager()
        self.broadcaster = Broadcaster.get_instance()
        self.screenshot_storage = ScreenshotStorage.get_instance()

    @staticmethod
    def _step_sort_key(form_def: FormDefinition) -> tuple[int, str]:
        return (form_def.step_order, str(form_def.id))

    def _order_form_definitions(self, form_defs: list[FormDefinition]) -> list[FormDefinition]:
        """Return form definitions in dependency order with a safe linear fallback."""
        ordered_by_step = sorted(form_defs, key=self._step_sort_key)
        if len(ordered_by_step) <= 1:
            return ordered_by_step

        step_to_def: dict[int, FormDefinition] = {}
        for form_def in ordered_by_step:
            if form_def.step_order in step_to_def:
                # Ambiguous dependency target, keep legacy linear behavior.
                return ordered_by_step
            step_to_def[form_def.step_order] = form_def

        children: dict[uuid.UUID, list[FormDefinition]] = {form_def.id: [] for form_def in ordered_by_step}
        indegree: dict[uuid.UUID, int] = {form_def.id: 0 for form_def in ordered_by_step}

        for form_def in ordered_by_step:
            dependency = getattr(form_def, "depends_on_step_order", None)
            if dependency is None:
                continue

            parent = step_to_def.get(dependency)
            if parent is None or parent.id == form_def.id:
                # Invalid graph, keep legacy linear behavior.
                return ordered_by_step

            children[parent.id].append(form_def)
            indegree[form_def.id] += 1

        for node_id in children:
            children[node_id].sort(key=self._step_sort_key)

        ready = sorted(
            [form_def for form_def in ordered_by_step if indegree[form_def.id] == 0],
            key=self._step_sort_key,
        )
        graph_order: list[FormDefinition] = []

        while ready:
            current = ready.pop(0)
            graph_order.append(current)

            for child in children[current.id]:
                indegree[child.id] -= 1
                if indegree[child.id] == 0:
                    ready.append(child)
            ready.sort(key=self._step_sort_key)

        if len(graph_order) != len(ordered_by_step):
            # Cycle detected, keep linear order to avoid hard failure on legacy data.
            return ordered_by_step

        return graph_order

    def _broadcast(self, event: str, data: dict):
        """Broadcast an execution event if user_id and execution are available."""
        if hasattr(self, '_user_id') and self._user_id and hasattr(self, '_execution_id') and self._execution_id:
            self.broadcaster.trigger_execution(self._user_id, str(self._execution_id), event, data)

    async def _vnc_pause(self, execution, steps_log, step_info, reason: str, browser) -> bool:
        """Activate VNC viewer and wait for user to resume.

        Uses the pre-reserved display session and activates x11vnc + websockify
        so the user can see and interact with the browser.
        Returns True if resumed successfully, False if timed out.
        """
        # Activate VNC on the reserved display (starts x11vnc + websockify)
        session_id = self._vnc_session_id
        vnc_result = await self.vnc_manager.activate_vnc(session_id)

        execution.status = 'waiting_manual'
        execution.vnc_session_id = session_id
        self.db.commit()

        step_info["status"] = "waiting_manual"
        step_info["waiting_reason"] = reason
        step_info["vnc_session_id"] = session_id
        step_info["vnc_url"] = vnc_result.get("vnc_url")
        step_info["ws_port"] = vnc_result.get("ws_port")
        steps_log.append(step_info)

        execution.steps_log = steps_log
        self.db.commit()

        # Broadcast waiting_manual event
        self._broadcast("execution.waiting_manual", {
            "task_id": str(execution.task_id),
            "status": "waiting_manual",
            "reason": reason,
            "vnc_session_id": session_id,
            "vnc_url": vnc_result.get("vnc_url"),
            "ws_port": vnc_result.get("ws_port"),
        })

        # WAIT for user to complete manual action and click resume
        resumed = await self.vnc_manager.wait_for_resume(session_id, timeout=3600)

        if not resumed:
            execution.status = 'failed'
            execution.error_message = f'VNC session timed out waiting for manual intervention ({reason})'
            execution.completed_at = datetime.now(UTC)
            execution.steps_log = steps_log
            self.db.commit()

            self._broadcast("execution.failed", {
                "task_id": str(execution.task_id),
                "status": "failed",
                "error": execution.error_message,
            })

            await browser.close()
            return False

        # User resumed - kill x11vnc and revoke token, keep Xvfb (browser still needs it)
        self.vnc_manager.deactivate_vnc(session_id)

        step_info["status"] = f"{reason}_resolved"
        execution.status = 'running'
        self.db.commit()

        # Replace the waiting_manual entry with updated step info
        steps_log[-1] = step_info

        # Broadcast resumed event
        self._broadcast("execution.resumed", {
            "task_id": str(execution.task_id),
            "status": "running",
            "reason": reason,
        })

        return True

    async def execute(self, task_id: str, execution_id: str = None,
                      is_dry_run: bool = False,
                      stealth_enabled: bool = True, user_agent: str = None,
                      action_delay_ms: int = 500) -> dict:
        """Execute a complete task flow."""

        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Store user_id for broadcasting
        self._user_id = task.user_id

        # Use existing execution record (created by Laravel) or create new one
        if execution_id:
            execution = self.db.query(ExecutionLog).filter(ExecutionLog.id == execution_id).first()
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")
            execution.status = 'running'
            execution.started_at = datetime.now(UTC)
            execution.steps_log = []
            self.db.commit()
        else:
            execution = ExecutionLog(
                id=uuid.uuid4(),
                task_id=task.id,
                started_at=datetime.now(UTC),
                status='running',
                is_dry_run=is_dry_run,
                steps_log=[],
                created_at=datetime.now(UTC)
            )
            self.db.add(execution)
            self.db.commit()

        self._execution_id = str(execution.id)

        # Broadcast execution started
        self._broadcast("execution.started", {
            "task_id": str(task.id),
            "status": "running",
            "is_dry_run": is_dry_run,
            "started_at": datetime.now(UTC).isoformat(),
        })

        steps_log = []

        # Check if any form needs VNC manual breakpoint - if so, use headed mode on Xvfb
        raw_form_defs = (self.db.query(FormDefinition)
            .filter(FormDefinition.task_id == task.id)
            .order_by(FormDefinition.step_order)
            .all())
        form_defs = self._order_form_definitions(raw_form_defs)

        needs_vnc = any(fd.human_breakpoint for fd in form_defs)

        # For VNC: reserve a display (starts only Xvfb) so Playwright can render.
        # x11vnc + websockify are started later only when a pause is actually needed.
        self._vnc_session_id = None
        if needs_vnc:
            reserved = await self.vnc_manager.reserve_display(str(execution.id))
            self._vnc_session_id = reserved["session_id"]
            self._vnc_display = reserved["display"]

        try:
            async with async_playwright() as p:
                launch_args = ["--no-sandbox", "--disable-setuid-sandbox"]

                if needs_vnc:
                    # Pass DISPLAY per-process via env param to avoid race conditions
                    # when multiple tasks run concurrently in the same async process
                    launch_env = {**os.environ, "DISPLAY": self._vnc_display}
                    launch_options = {"headless": False, "args": launch_args, "env": launch_env}
                else:
                    launch_options = {"headless": True, "args": launch_args}

                browser = await p.chromium.launch(**launch_options)

                context_options = {}
                if user_agent:
                    context_options["user_agent"] = user_agent

                context = await browser.new_context(**context_options)

                if stealth_enabled:
                    await apply_stealth(context)

                page = await context.new_page()

                for i, form_def in enumerate(form_defs):
                    step_info = {
                        "step": form_def.step_order,
                        "depends_on_step_order": form_def.depends_on_step_order,
                        "page_url": form_def.page_url,
                        "form_type": form_def.form_type,
                        "status": "started",
                        "timestamp": datetime.now(UTC).isoformat()
                    }

                    # Broadcast step started
                    self._broadcast("execution.step_started", {
                        "task_id": str(task.id),
                        "step": form_def.step_order,
                        "total_steps": len(form_defs),
                        "page_url": form_def.page_url,
                        "form_type": form_def.form_type,
                    })

                    # Navigate with resilient waits; "networkidle" can block on
                    # modern pages that keep background connections open.
                    await page.goto(form_def.page_url, wait_until="domcontentloaded", timeout=45000)
                    try:
                        await page.wait_for_load_state("load", timeout=15000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(800)

                    step_info["navigated"] = True

                    # Wait for form (if form_selector is specified)
                    if form_def.form_selector:
                        try:
                            await page.wait_for_selector(form_def.form_selector, timeout=10000)
                        except Exception:
                            step_info["status"] = "form_not_found"
                            step_info["error"] = f"Form selector '{form_def.form_selector}' not found"
                            steps_log.append(step_info)
                            raise Exception(step_info["error"])

                    # Fill form fields
                    fields = (self.db.query(FormField)
                        .filter(FormField.form_definition_id == form_def.id)
                        .order_by(FormField.sort_order)
                        .all())

                    for field in fields:
                        if field.preset_value is None:
                            continue

                        value = field.preset_value

                        # Decrypt sensitive values
                        if field.is_sensitive and settings.encryption_key:
                            try:
                                fernet = Fernet(settings.encryption_key.encode())
                                value = fernet.decrypt(value.encode()).decode()
                            except Exception:
                                pass

                        try:
                            if field.field_type == 'hidden':
                                await page.eval_on_selector(
                                    field.field_selector,
                                    "(el, val) => el.value = val", value
                                )
                            elif field.is_file_upload:
                                file_path = os.path.join(settings.upload_dir, value)
                                await page.set_input_files(field.field_selector, file_path)
                            elif field.field_type in ('select',):
                                await page.select_option(field.field_selector, value)
                            elif field.field_type == 'checkbox':
                                if value.lower() in ('true', '1', 'yes', 'on'):
                                    await page.check(field.field_selector)
                                else:
                                    await page.uncheck(field.field_selector)
                            elif field.field_type == 'radio':
                                await page.check(f'{field.field_selector}[value="{value}"]')
                            else:
                                await page.fill(field.field_selector, value)

                            # Wait between actions
                            await page.wait_for_timeout(action_delay_ms)

                            # Broadcast field filled
                            self._broadcast("execution.field_filled", {
                                "task_id": str(task.id),
                                "step": form_def.step_order,
                                "field_name": field.field_name,
                                "field_type": field.field_type,
                            })

                        except Exception as e:
                            step_info[f"field_{field.field_name}_error"] = str(e)

                    # Human breakpoint: pause for manual review after filling
                    if form_def.human_breakpoint:
                        resumed = await self._vnc_pause(
                            execution, steps_log, step_info, "breakpoint", browser
                        )
                        if not resumed:
                            return {
                                "execution_id": str(execution.id),
                                "status": "failed",
                                "error": "VNC timeout (breakpoint)"
                            }

                    # Check if this is the last step and dry run
                    is_last_step = (i == len(form_defs) - 1)

                    if is_dry_run and is_last_step:
                        screenshot_name = f"{execution.id}_dryrun.png"
                        screenshot_path = os.path.join(settings.screenshot_dir, screenshot_name)
                        await page.screenshot(path=screenshot_path, full_page=True)

                        # Upload to MinIO
                        screenshot_url = None
                        screenshot_size = None
                        try:
                            screenshot_url, screenshot_size = self.screenshot_storage.upload_screenshot(
                                screenshot_path, str(task.user_id), str(execution.id)
                            )
                        except Exception as e:
                            logger.warning(f"Failed to upload dry-run screenshot to MinIO: {e}")

                        step_info["status"] = "dry_run_complete"
                        steps_log.append(step_info)

                        execution.status = 'dry_run_ok'
                        execution.screenshot_path = screenshot_name
                        execution.screenshot_url = screenshot_url
                        execution.screenshot_size = screenshot_size
                        execution.completed_at = datetime.now(UTC)
                        execution.steps_log = steps_log
                        self.db.commit()

                        self._broadcast("execution.completed", {
                            "task_id": str(task.id),
                            "status": "dry_run_ok",
                            "screenshot": screenshot_name,
                        })

                        await browser.close()
                        return {
                            "execution_id": str(execution.id),
                            "status": "dry_run_ok",
                            "screenshot": screenshot_name,
                            "screenshot_url": screenshot_url
                        }

                    # Submit form
                    try:
                        await page.click(form_def.submit_selector)
                        try:
                            await page.wait_for_load_state("load", timeout=15000)
                        except Exception:
                            await page.wait_for_timeout(2000)
                        await page.wait_for_timeout(800)
                        step_info["status"] = "submitted"
                    except Exception as e:
                        step_info["status"] = "submit_error"
                        step_info["error"] = str(e)

                    # Only append if not already added by _vnc_pause
                    if not steps_log or steps_log[-1] is not step_info:
                        steps_log.append(step_info)

                    # Broadcast step completed
                    self._broadcast("execution.step_completed", {
                        "task_id": str(task.id),
                        "step": form_def.step_order,
                        "total_steps": len(form_defs),
                        "status": step_info["status"],
                    })

                # Wait for any final navigation to complete after last submit
                try:
                    await page.wait_for_load_state("load", timeout=15000)
                except Exception:
                    pass
                await page.wait_for_timeout(1000)

                # Take final screenshot
                screenshot_name = f"{execution.id}_final.png"
                screenshot_path = os.path.join(settings.screenshot_dir, screenshot_name)
                await page.screenshot(path=screenshot_path, full_page=True)

                # Upload to MinIO
                screenshot_url = None
                screenshot_size = None
                try:
                    screenshot_url, screenshot_size = self.screenshot_storage.upload_screenshot(
                        screenshot_path, str(task.user_id), str(execution.id)
                    )
                except Exception as e:
                    logger.warning(f"Failed to upload screenshot to MinIO: {e}")

                await browser.close()

            # Update execution log - success
            execution.status = 'success'
            execution.screenshot_path = screenshot_name
            execution.screenshot_url = screenshot_url
            execution.screenshot_size = screenshot_size
            execution.completed_at = datetime.now(UTC)
            execution.steps_log = steps_log
            self.db.commit()

            self._broadcast("execution.completed", {
                "task_id": str(task.id),
                "status": "success",
                "screenshot": screenshot_name,
            })

            return {
                "execution_id": str(execution.id),
                "status": "success",
                "screenshot": screenshot_name,
                "screenshot_url": screenshot_url
            }

        except Exception as e:
            # Update execution log - failed
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = datetime.now(UTC)
            execution.steps_log = steps_log
            self.db.commit()

            self._broadcast("execution.failed", {
                "task_id": str(task.id),
                "status": "failed",
                "error": str(e),
            })

            return {
                "execution_id": str(execution.id),
                "status": "failed",
                "error": str(e)
            }
        finally:
            # Always cleanup VNC session (Xvfb + x11vnc) regardless of outcome
            if self._vnc_session_id:
                try:
                    await self.vnc_manager.stop_session(self._vnc_session_id)
                except Exception:
                    pass
                self._vnc_session_id = None
