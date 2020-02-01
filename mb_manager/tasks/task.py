from __future__ import annotations

import abc
import asyncio
import logging

from typing import Any, Set, Dict, List, Type, Tuple, Optional

from aiohttp import web

log = logging.getLogger(__name__)


class Task(type):
    def __init__(cls: type, name: str, bases: Tuple[type, ...], dct: Dict[str, Any]):
        for base in cls.__mro__:
            if "interval" in base.__dict__:
                cls._instances.add(cls())  # type: ignore


class BaseTask(metaclass=Task):
    _instances: Set[BaseTask] = set()

    interval: int

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._cancelled = False

    async def setup(self, app: web.Application) -> None:
        pass

    async def stop(self) -> None:
        pass

    @staticmethod
    async def schedule_all(app: web.Application) -> None:
        log.info(f"scheduling {len(BaseTask._instances)} tasks")

        for instance in BaseTask._instances:
            await instance.schedule(app)

    async def schedule(self, app: web.Application) -> None:
        await self.setup(app)

        self._task = asyncio.create_task(self._run_forever())

    async def _run_forever(self) -> None:
        while not self._cancelled:
            log.debug("running task %s", self.__class__.__name__)

            try:
                await self.run_once()
            except Exception:
                log.exception("error running task")

            await asyncio.sleep(self.interval)

    @abc.abstractmethod
    async def run_once(self) -> None:
        raise NotImplementedError

    @staticmethod
    async def cancel_all(_: web.Application) -> None:
        log.info(f"cancelling {len(BaseTask._instances)} tasks")

        for instance in BaseTask._instances:
            await instance.stop()

    async def cancel(self) -> None:
        self._cancelled = True

        await self.stop()

        if self._task:
            self._task.cancel()
