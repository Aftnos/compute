from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


@dataclass
class ScheduledJob:
    job_id: str
    description: str


class SchedulerManager:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._jobs: Dict[str, ScheduledJob] = {}

    def schedule_daily(self, job_id: str, time_expression: str, callback: Callable[[], None]) -> None:
        hour, minute = [int(part) for part in time_expression.split(":", maxsplit=1)]
        trigger = CronTrigger(hour=hour, minute=minute)
        self._add_job(job_id, trigger, callback, f"daily@{time_expression}")

    def schedule_weekly(self, job_id: str, expression: str, callback: Callable[[], None]) -> None:
        days_part, time_part = expression.split("@", maxsplit=1)
        hour, minute = [int(part) for part in time_part.split(":", maxsplit=1)]
        trigger = CronTrigger(day_of_week=days_part, hour=hour, minute=minute)
        self._add_job(job_id, trigger, callback, f"weekly@{expression}")

    def schedule_cron(self, job_id: str, cron_expression: str, callback: Callable[[], None]) -> None:
        trigger = CronTrigger.from_crontab(cron_expression)
        self._add_job(job_id, trigger, callback, f"cron@{cron_expression}")

    def remove_job(self, job_id: str) -> None:
        if job_id in self._jobs:
            self._scheduler.remove_job(job_id)
            self._jobs.pop(job_id)

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
        self._jobs.clear()

    def _add_job(self, job_id: str, trigger: CronTrigger, callback: Callable[[], None], desc: str) -> None:
        if job_id in self._jobs:
            self.remove_job(job_id)
        self._scheduler.add_job(callback, trigger=trigger, id=job_id, replace_existing=True)
        self._jobs[job_id] = ScheduledJob(job_id=job_id, description=desc)
