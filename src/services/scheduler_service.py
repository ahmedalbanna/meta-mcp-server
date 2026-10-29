"""Scheduler service (Phase B)."""

from __future__ import annotations

import contextlib
from typing import Any

from src.core.services import Services
from src.scheduler import SCHEDULE_FILE, _load_tasks, _save_tasks


class SchedulerService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def list_scheduled_tasks(self, status: str = "") -> dict[str, Any]:
        tasks = _load_tasks()
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return {"tasks": tasks, "count": len(tasks), "file": str(SCHEDULE_FILE)}

    def get_scheduled_task(self, task_id: str) -> dict[str, Any] | None:
        tasks = _load_tasks()
        for t in tasks:
            if t.get("id") == task_id:
                return t
        return None

    def cancel_scheduled_task(self, task_id: str) -> dict[str, Any]:
        tasks = _load_tasks()
        orig = len(tasks)
        tasks = [t for t in tasks if t.get("id") != task_id]
        if len(tasks) == orig:
            raise ValueError(f"المهمة {task_id} غير موجودة")
        _save_tasks(tasks)
        try:
            from src.scheduler import _get_apscheduler
            sched = _get_apscheduler()
            if sched is not None:
                with contextlib.suppress(Exception):
                    sched.remove_job(task_id)
        except Exception:
            pass
        return {"success": True, "cancelled": task_id, "remaining": len(tasks)}

    def schedule_task(self, name: str, tool_name: str, params_json: str = "", run_at: int = 0,
                      cron: str = "") -> dict[str, Any]:
        import json as _json
        import time
        import uuid
        if not tool_name:
            raise ValueError("tool_name مطلوب")
        params = {}
        if params_json:
            try:
                params = _json.loads(params_json)
                if not isinstance(params, dict):
                    raise ValueError("params_json يجب أن يكون كائن JSON")
            except (_json.JSONDecodeError, ValueError):
                raise ValueError("params_json ليس JSON صالح") from None
        if cron:
            try:
                from apscheduler.triggers.cron import CronTrigger  # type: ignore
                CronTrigger.from_crontab(cron)
            except ImportError:
                raise ValueError("cron يتطلب APScheduler. ثبّت: pip install apscheduler") from None
            except Exception as e:
                raise ValueError(f"cron غير صالح: {e}") from None
        elif run_at == 0:
            run_at = int(time.time()) + 60
        task_id = uuid.uuid4().hex[:10]
        task = {
            "id": task_id, "name": name, "tool_name": tool_name, "params": params,
            "run_at": run_at, "cron": cron, "created_at": int(time.time()), "status": "scheduled",
        }
        tasks = _load_tasks()
        tasks.append(task)
        _save_tasks(tasks)
        try:
            from datetime import datetime as _dt

            from src.scheduler import _dispatch_tool, _get_apscheduler
            sched = _get_apscheduler()
            if sched is not None:
                if cron:
                    sched.add_job(_dispatch_tool, "cron", id=task_id, name=name,
                                  args=[tool_name, params], replace_existing=True)
                elif run_at:
                    run_date = _dt.fromtimestamp(run_at)
                    sched.add_job(_dispatch_tool, "date", run_date=run_date, id=task_id,
                                  name=name, args=[tool_name, params], replace_existing=True)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("APScheduler persist failed (fallback to JSON): %s", e)
        return {"success": True, "task": task, "total": len(tasks), "apscheduler": _get_apscheduler() is not None}
