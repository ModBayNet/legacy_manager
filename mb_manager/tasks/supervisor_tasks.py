import asyncio
import logging

import aiohttp

from aiohttp import web

from .task import BaseTask
from ..docker import Docker, DockerException

# add class into this list to enable task
__all__ = ("HTTPSupervisor",)

log = logging.getLogger(__name__)

WORKER_CONTAINER_NAME = "modbay-worker.service"


class HTTPSupervisor(BaseTask):
    interval = 60

    async def setup(self, app: web.Application) -> None:
        await super().setup(app)

        self._session = aiohttp.ClientSession()

        self._healthcheck_url = app["config"]["supervisor"]["healthcheck_url"]

    async def stop(self) -> None:
        await self._session.close()

    async def run_once(self) -> None:
        try:
            async with self._session.get(self._healthcheck_url) as r:
                if r.status == 200:
                    return

                log.error(f"{r.method} {r.url}: {r.status}")
        except aiohttp.ClientConnectionError:
            log.exception("service unreachable")


class DockerSupervisor(BaseTask):
    interval = 5

    async def setup(self, app: web.Application) -> None:
        await super().setup(app)

        self._docker: Docker = app["docker"]

    async def run_once(self) -> None:
        try:
            await self._docker.wait(WORKER_CONTAINER_NAME, condition="removed")
        except DockerException as e:
            if e.status == 404:
                log.warning("container does not exist, creating")
            else:
                log.exception("error waiting container")

        HTTPSupervisor.pause()
        await self._create_container()
        HTTPSupervisor.unpause()

    # TODO: move to Docker class
    async def _create_container(self) -> None:
        create_params = {"name": WORKER_CONTAINER_NAME}
        create_body = {
            "User": "root",  # TODO: do not use root?
            "Cmd": ("-v", "debug"),
            "Image": "registry.gitlab.com/modbay1/worker",
            "HostConfig": {
                "Binds": ("/home/modbay/worker_config.yaml:/code/config.yaml",),
                "PortBindings": {
                    "8080/tcp": ({"HostIp": "127.0.0.1", "HostPort": "8080"},)
                },
                "AutoRemove": True,
            },
        }

        await self._docker.request(
            "POST", "/containers/create", params=create_params, body=create_body
        )
        await self._docker.request(
            "POST", f"/containers/{WORKER_CONTAINER_NAME}/start",
        )
