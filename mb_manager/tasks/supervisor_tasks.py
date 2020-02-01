import logging

import aiohttp

from aiohttp import web

from .task import BaseTask

# add class into this list to enable task
__all__ = ("HTTPSupervisor",)

log = logging.getLogger(__name__)


class HTTPSupervisor(BaseTask):
    interval = 60

    async def setup(self, app: web.Application) -> None:
        self._session = aiohttp.ClientSession()

        self._healthcheck_url = app["config"]["supervisor"]["healthcheck_url"]

    async def stop(self) -> None:
        await self._session.close()

    async def run_once(self) -> None:
        async with self._session.get(self._healthcheck_url) as r:
            if r.status == 200:
                return

            # TODO: sentry event
            log.error(f"{r.method} {r.url}: {r.status}")
