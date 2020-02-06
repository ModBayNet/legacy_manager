from __future__ import annotations

import json
import asyncio
import logging

from base64 import b64encode
from typing import Any, Mapping, Optional

import aiohttp

from sentry_sdk import push_scope

DOCKER_API_VERSION = "1.40"

log = logging.getLogger(__name__)


class DockerException(Exception):
    def __init__(self, url: str, status: int, msg: str):
        self.url = url
        self.status = status

        super().__init__(msg)


class Docker:
    def __init__(
        self, *, session: aiohttp.ClientSession, registry_address: str, **kwargs: Any,
    ):
        self._session = session
        self.registry_address = registry_address

        self._url_base = f"unix://{DOCKER_API_VERSION}"

    # Looks like gitlab does not support IdentityToken yet
    #
    # async def _registry_authorize(self, credentials: Mapping[str, Any]) -> str:
    #     response = await self.request("POST", "auth", body={**credentials},)
    #
    #     return response["IdentityToken"]

    def _make_registry_auth_header(
        self, registry_credentials: Mapping[str, Any]
    ) -> str:
        dumped = json.dumps(
            {"serveraddress": self.registry_address, **registry_credentials}
        )

        return b64encode(dumped.encode()).decode()

    @classmethod
    async def connect(cls, *, socket: str, **kwargs: Any) -> Docker:
        # TODO: support for other connectors?
        session = aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=socket))

        docker = Docker(session=session, **kwargs)

        # docker._token = await docker._registry_authorize(registry_credentials)

        return docker

    @staticmethod
    async def _read_response(resp: aiohttp.ClientResponse) -> Any:
        content = await resp.read()

        # Docker HTTP API returns \r\n separated list of json objects in response to
        # /images/create for some reason
        # Also last item can be empty (not sure if it always is)
        return [json.loads(i) for i in content.split(b"\r\n")[:-1]]

    async def request(
        self,
        method: str = "GET",
        path: str = "",
        params: Mapping[str, Any] = {},
        body: Any = None,
        registry_credentials: Mapping[str, Any] = {},
        **kwargs: Any,
    ) -> Any:
        url = f"{self._url_base}{path}"
        log.info("%6s: %s", method, url)

        headers = {}
        if registry_credentials:
            headers["X-Registry-Auth"] = self._make_registry_auth_header(
                registry_credentials
            )

        async with self._session.request(
            method, url, params=params, json=body, headers=headers, **kwargs
        ) as resp:
            if resp.status // 100 not in (2, 3):
                decoded = await resp.json()
                with push_scope() as scope:
                    scope.set_extra("request", body)
                    scope.set_extra("response", decoded)

                raise DockerException(url, resp.status, decoded["message"])

            if resp.status == 204:
                decoded = {}
            else:
                decoded = await self._read_response(resp)

            if isinstance(decoded, dict):
                warnings = decoded.get("Warnings")
                if warnings:
                    log.warn(f"docker warning(s): {warnings}")

            return decoded

    async def pull(
        self,
        image: str,
        tag: str = "latest",
        registry_credentials: Mapping[str, Any] = {},
    ) -> None:
        await self.request(
            "POST",
            "/images/create",
            params=dict(fromImage=image, tag=tag,),
            registry_credentials=registry_credentials,
        )

    async def restart(self, name: str) -> None:
        await self.request("POST", f"/containers/{name}/restart")

    async def wait(self, name: str, condition: str = "not-running") -> None:
        await self.request(
            "POST",
            f"/containers/{name}/wait",
            params=dict(condition=condition),
            timeout=None,
        )

    async def close(self) -> None:
        await self._session.close()


async def _connect(app: aiohttp.web.Application) -> None:
    log.debug("connecting to docker")

    docker_config = app["config"]["docker"]
    app["docker"] = await Docker.connect(
        socket=docker_config["socket"],
        registry_address=docker_config["registry"]["address"],
    )
    app["docker_ready"].set()


async def _disconnect(app: aiohttp.web.Application) -> None:
    log.debug("disconnecting from docker")

    app["docker_ready"].clear()

    await app["docker"].close()


def setup(app: aiohttp.web.Application) -> None:
    # useless without reconnect logic
    app["docker_ready"] = asyncio.Event()

    app.on_startup.append(_connect)
    app.on_cleanup.append(_disconnect)
