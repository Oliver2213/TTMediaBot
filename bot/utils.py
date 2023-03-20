import os
from typing import List, Tuple
from crontab import CronTab

from bot import app_vars
from bot.config.models import CronEntryModel


def clean_file_name(file_name: str) -> str:
    for char in ["\\", "/", "%", "*", "?", ":", '"', "|"] + [
        chr(i) for i in range(1, 32)
    ]:
        file_name = file_name.replace(char, "_")
    file_name = file_name.strip()
    return file_name


def get_abs_path(file_name: str) -> str:
    return os.path.join(app_vars.directory, file_name)


def sort_cron_tasks(tasks: List[Tuple[CronTab, CronEntryModel]]) -> List[CronEntryModel]:
    """Given a list of CronTask instances, return the same list, sorted by ascending next run time."""
    # sort by item[0].next(), a function on CronTab instance
    sorted_tasks = sorted(tasks, key=lambda t: t[0].next())
    return sorted_tasks
