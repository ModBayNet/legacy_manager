from aiohttp import web

from .task import BaseTask
from .supervisor_tasks import *


def setup(app: web.Application) -> None:
    app.on_startup.append(BaseTask.schedule_all)
    app.on_cleanup.append(BaseTask.cancel_all)
