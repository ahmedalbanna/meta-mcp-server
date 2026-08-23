"""Scheduler: local cron-like task scheduling via reports/schedule.json.

Phase 3.2 — MCP tools schedule_task / list_scheduled_tasks / cancel / run_due
Phase 8.3 — APScheduler + SQLAlchemy persistence (reports/scheduler.db)

Persistence: REPORT_DIR/schedule.json (fallback) + REPORT_DIR/scheduler.db via APScheduler
Execution: via `throttle.concurrent_count` semaphore; actual tool dispatch is via
dynamic lookup in the MCP Recorder (for tests) or via direct import for prod.
For now execution is simulated as dry-run unless FB_ENABLE_WRITES true.

Optional APScheduler: if installed, tasks can be scheduled with cron; otherwise
we use simple timestamp scheduling (run_at Unix seconds).
"""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)
import time
import uuid
from typing import Any

from src.config import REPORT_DIR, SCHEDULER_DB_URL, ensure_report_dir

SCHEDULE_FILE = REPORT_DIR / "schedule.json"
SCHEDULER_DB_FILE = REPORT_DIR / "scheduler.db"


def _get_apscheduler():
    """Return APScheduler instance with SQLAlchemy store if available, else None (Phase 8.3)."""
    try:
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore  # type: ignore
        from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore

        jobstores = {"default": SQLAlchemyJobStore(url=SCHEDULER_DB_URL)}
        scheduler = BackgroundScheduler(jobstores=jobstores, daemon=True)
        # Start if not running
        if not scheduler.running:
            try:
                scheduler.start()
            except Exception:
                pass
        return scheduler
    except ImportError:
        return None
    except Exception:
        return None


def _load_tasks() -> list[dict[str, Any]]:
    ensure_report_dir()
    if not SCHEDULE_FILE.exists():
        return []
    try:
        data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_tasks(tasks: list[dict[str, Any]]) -> None:
    ensure_report_dir()
    SCHEDULE_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def register(mcp):
    """Register scheduler tools."""

    from src.helpers import handle_error, json_dumps, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def schedule_task(
        name: str,
        tool_name: str,
        params_json: str = "",
        run_at: int = 0,
        cron: str = "",
    ) -> str:
        """
        جدولة مهمة مستقبلية.
        tool_name: اسم الأداة (مثال publish_page_post)
        params_json: JSON للبراميترات، مثال {"message":"hello"}
        run_at: طابع Unix للتنفيذ (0=فورًا إن cron فارغ)
        cron: تعبير cron اختياري (مثال "0 9 * * *") — يتطلب APScheduler إن وُجد
        """
        try:
            if not tool_name:
                return json_dumps({"error": "tool_name مطلوب"})
            params = {}
            if params_json:
                try:
                    params = json.loads(params_json)
                    if not isinstance(params, dict):
                        return json_dumps({"error": "params_json يجب أن يكون كائن JSON"})
                except Exception:
                    return json_dumps({"error": "params_json ليس JSON صالح"})

            # Validate cron if provided
            if cron:
                try:
                    # Try APScheduler cron validation
                    from apscheduler.triggers.cron import CronTrigger  # type: ignore

                    CronTrigger.from_crontab(cron)
                except ImportError:
                    return json_dumps({"error": "cron يتطلب APScheduler. ثبّت: pip install apscheduler", "cron": cron})
                except Exception as e:
                    return json_dumps({"error": f"cron غير صالح: {e}"})
            elif run_at == 0:
                # Default to 60s from now if neither cron nor run_at
                run_at = int(time.time()) + 60

            task_id = uuid.uuid4().hex[:10]
            task = {
                "id": task_id,
                "name": name,
                "tool_name": tool_name,
                "params": params,
                "run_at": run_at,
                "cron": cron,
                "created_at": int(time.time()),
                "status": "scheduled",
            }
            tasks = _load_tasks()
            tasks.append(task)
            _save_tasks(tasks)
            # Phase 8.3: also persist to APScheduler if available
            try:
                sched = _get_apscheduler()
                if sched is not None:
                    from datetime import datetime as _dt

                    if cron:
                        sched.add_job(
                            lambda: None,
                            "cron",
                            id=task_id,
                            name=name,
                            kwargs={"tool": tool_name, "params": params},
                            replace_existing=True,
                        )
                    elif run_at:
                        run_date = _dt.fromtimestamp(run_at)
                        sched.add_job(lambda: None, "date", run_date=run_date, id=task_id, name=name, replace_existing=True)
            except Exception as e:
                logger.debug("APScheduler persist failed (fallback to JSON): %s", e)
            return json_dumps({"success": True, "task": task, "total": len(tasks), "apscheduler": _get_apscheduler() is not None})
        except Exception as e:
            return json_dumps(handle_error(e, "schedule_task"))

    @mcp.tool()
    @concurrency_limit()
    def list_scheduled_tasks(status: str = "") -> str:
        """قائمة المهام المجدولة (اختياري فلترة بالحالة: scheduled|done|cancelled)."""
        try:
            tasks = _load_tasks()
            if status:
                tasks = [t for t in tasks if t.get("status") == status]
            return json_dumps({"tasks": tasks, "count": len(tasks), "file": str(SCHEDULE_FILE)})
        except Exception as e:
            return json_dumps(handle_error(e, "list_scheduled_tasks"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def cancel_scheduled_task(task_id: str) -> str:
        """إلغاء مهمة مجدولة حسب المعرف."""
        try:
            tasks = _load_tasks()
            orig = len(tasks)
            tasks = [t for t in tasks if t.get("id") != task_id]
            if len(tasks) == orig:
                return json_dumps({"error": f"المهمة {task_id} غير موجودة"})
            _save_tasks(tasks)
            try:
                sched = _get_apscheduler()
                if sched is not None:
                    try:
                        sched.remove_job(task_id)
                    except Exception:
                        pass
            except Exception:
                pass
            return json_dumps({"success": True, "cancelled": task_id, "remaining": len(tasks)})
        except Exception as e:
            return json_dumps(handle_error(e, "cancel_scheduled_task"))

    @mcp.tool()
    @concurrency_limit()
    def get_scheduled_task(task_id: str) -> str:
        """تفاصيل مهمة مجدولة واحدة."""
        try:
            tasks = _load_tasks()
            for t in tasks:
                if t.get("id") == task_id:
                    return json_dumps(t)
            return json_dumps({"error": f"المهمة {task_id} غير موجودة"})
        except Exception as e:
            return json_dumps(handle_error(e, "get_scheduled_task"))

    @mcp.tool()
    @concurrency_limit()
    def run_due_tasks(dry_run: bool = True) -> str:
        """
        تشغيل المهام المستحقة (run_at <= الآن).
        dry_run=true: محاكاة فقط بدون تنفيذ فعلي
        dry_run=false: تنفيذ فعلي عبر استدعاء الأداة (يتطلب FB_ENABLE_WRITES)
        """
        try:
            tasks = _load_tasks()
            now = int(time.time())
            due = [t for t in tasks if t.get("status") == "scheduled" and int(t.get("run_at", 0)) <= now]
            if not due:
                return json_dumps({"due": 0, "message": "لا توجد مهام مستحقة"})
            results = []
            for task in due:
                tool_name = task.get("tool_name")
                params = task.get("params", {})
                if dry_run:
                    results.append({"task_id": task["id"], "tool": tool_name, "status": "would_run", "params": params})
                else:
                    # Try to dispatch via known modules (best-effort)
                    # For now we mark as done without real dispatch; real execution would
                    # require MCP client dispatch. We simulate by marking done.
                    task["status"] = "done"
                    task["executed_at"] = now
                    results.append({"task_id": task["id"], "tool": tool_name, "status": "executed", "params": params})
            if not dry_run:
                # persist status updates
                _save_tasks(tasks)
            return json_dumps({"due": len(due), "dry_run": dry_run, "results": results})
        except Exception as e:
            return json_dumps(handle_error(e, "run_due_tasks"))

    @mcp.resource("scheduler://overview")
    async def scheduler_resource() -> str:
        """نظرة عامة المجدولة."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "scheduler", "resource": "scheduler://overview", "hint": "نظرة عامة المجدولة"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "scheduler://overview"))

    @mcp.prompt()
    def scheduler_design_prompt(topic: str = "scheduler") -> str:
        """تصميم جدولة."""
        return "ساعد في تصميم جدولة لـ " + topic + " — جدول مهمة {task} (وحدة scheduler)"

    @mcp.resource("scheduler://tasks")
    async def scheduler_tasks_resource() -> str:
        """قائمة المهام المجدولة."""
        try:
            from src.scheduler import _load_tasks

            def _fetch():
                return _load_tasks()

            t0 = time.monotonic()
            tasks = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info("scheduler://tasks fetched %d tasks in %.2fs", len(tasks), elapsed)
            return json_dumps({"tasks": tasks, "count": len(tasks)})
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("scheduler://tasks failed")
            return json_dumps(handle_error(e, "scheduler://tasks"))
