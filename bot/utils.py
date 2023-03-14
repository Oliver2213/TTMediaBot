import os
from operator import methodcaller
from typing import List

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


def sorted_cron_tasks(tasks: List[CronEntryModel]) -> List[CronEntryModel]:
    """Given a list of CronTask instances, return the same list, sorted by ascending next run time."""
    clean_tasks: List[CronEntryModel] = []
    for t in tasks:
        if t.valid_pattern():
            clean_tasks.append(t)
    sorted_tasks = sorted(clean_tasks, key=methodcaller("next"))
    return sorted_tasks
