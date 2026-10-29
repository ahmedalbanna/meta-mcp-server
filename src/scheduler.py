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
from typing import Any

from src.config import REPORT_DIR, SCHEDULER_DB_URL, ensure_report_dir

SCHEDULE_FILE = REPORT_DIR / "schedule.json"
SCHEDULER_DB_FILE = REPORT_DIR / "scheduler.db"

_MODULES = [
    "ads",
    "adsets",
    "audiences",
    "automation",
    "breakdowns",
    "business",
    "campaigns",
    "catalog",
    "creatives",
    "discovery",
    "events",
    "finance",
    "insights",
    "instagram",
    "leads",
    "messenger",
    "metrics",
    "pages",
    "reports",
    "webhook_automations",
    "whatsapp",
]


class _Recorder:
    def tool(self, *args, **kwargs):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator

    def resource(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def prompt(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def __init__(self):
        self.tools = {}


_TOOL_CACHE: dict[str, Any] = {}


def _dispatch_tool(tool_name: str, params: dict) -> Any:
    if tool_name in _TOOL_CACHE:
        return _TOOL_CACHE[tool_name](**params)
    import importlib

    for mod_name in _MODULES:
        try:
            mod = importlib.import_module(f"src.{mod_name}")
            rec = _Recorder()
            mod.register(rec)
            if tool_name in rec.tools:
                _TOOL_CACHE[tool_name] = rec.tools[tool_name]
                return rec.tools[tool_name](**params)
        except Exception:
            continue
    raise ValueError(f"أداة غير معروفة: {tool_name}")


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


def register(mcp, services=None):
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
            from src.core.services import Services
            from src.services.scheduler_service import SchedulerService
            svc = SchedulerService(services) if services is not None else SchedulerService(Services.default())
            return json_dumps(svc.schedule_task(name, tool_name, params_json, run_at, cron))
        except Exception as e:
            return json_dumps(handle_error(e, "schedule_task"))

    @mcp.tool()
    @concurrency_limit()
    def list_scheduled_tasks(status: str = "") -> str:
        """قائمة المهام المجدولة (اختياري فلترة بالحالة: scheduled|done|cancelled)."""
        try:
            from src.core.services import Services
            from src.services.scheduler_service import SchedulerService
            svc = SchedulerService(services) if services is not None else SchedulerService(Services.default())
            return json_dumps(svc.list_scheduled_tasks(status))
        except Exception as e:
            return json_dumps(handle_error(e, "list_scheduled_tasks"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def cancel_scheduled_task(task_id: str) -> str:
        """إلغاء مهمة مجدولة حسب المعرف."""
        try:
            from src.core.services import Services
            from src.services.scheduler_service import SchedulerService
            svc = SchedulerService(services) if services is not None else SchedulerService(Services.default())
            return json_dumps(svc.cancel_scheduled_task(task_id))
        except Exception as e:
            return json_dumps(handle_error(e, "cancel_scheduled_task"))

    @mcp.tool()
    @concurrency_limit()
    def get_scheduled_task(task_id: str) -> str:
        """تفاصيل مهمة مجدولة واحدة."""
        try:
            from src.core.services import Services
            from src.services.scheduler_service import SchedulerService
            svc = SchedulerService(services) if services is not None else SchedulerService(Services.default())
            task = svc.get_scheduled_task(task_id)
            if task is None:
                return json_dumps({"error": f"المهمة {task_id} غير موجودة"})
            return json_dumps(task)
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
                tool_name = task.get("tool_name") or ""
                params = task.get("params") or {}
                if dry_run:
                    results.append({"task_id": task["id"], "tool": tool_name, "status": "would_run", "params": params})
                else:
                    try:
                        _dispatch_tool(tool_name, params)
                        task["status"] = "done"
                        task["executed_at"] = now
                        results.append({"task_id": task["id"], "tool": tool_name, "status": "executed", "params": params})
                    except Exception as e:
                        task["status"] = "failed"
                        task["error"] = str(e)
                        results.append({"task_id": task["id"], "tool": tool_name, "status": "error", "error": str(e)})
            if not dry_run:
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
