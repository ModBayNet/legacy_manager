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
                instance = cls()
                cls._instance = instance
                cls._instances.add(instance)  # type: ignore


class BaseTask(metaclass=Task):
    _instance: BaseTask
    _instances: Set[BaseTask] = set()

    interval: int

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._cancelled = False

        # cannot be set here because aiohttp starts a thread that breaks asyncio
        self._unpaused: asyncio.Event

    async def setup(self, app: web.Application) -> None:
        self._unpaused = asyncio.Event()
        self._unpaused.set()

    async def stop(self) -> None:
        pass

    @classmethod
    def _get_instance(cls) -> BaseTask:
        return cls._instance

    @classmethod
    def pause(cls) -> None:
        log.debug("task %s paused", cls.__name__)

        cls._get_instance()._unpaused.clear()

    @classmethod
    def unpause(cls) -> None:
        log.debug("task %s unpaused", cls.__name__)

        cls._get_instance()._unpaused.set()

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
            # sleeping before task gives supervisor tasks small buffer of time that lets
            # them not flood Sentry with false errors while backend is booting
            await asyncio.sleep(self.interval)

            await self._unpaused.wait()

            log.debug("running task %s", self.__class__.__name__)
            try:
                await self.run_once()
            except Exception:
                log.exception("error running task")

    @abc.abstractmethod
    async def run_once(self) -> None:
        raise NotImplementedError

    @staticmethod
    async def cancel_all(_: web.Application) -> None:
        log.info(f"cancelling {len(BaseTask._instances)} tasks")

        for instance in BaseTask._instances:
            await instance.stop()

    async def cancel(self) -> None:
        if self._cancelled:
            return

        self._cancelled = True

        await self.stop()

        if self._task:
            self._task.cancel()
