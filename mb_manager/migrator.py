import os
import sys
import logging

import edgedb

from aiohttp import web

log = logging.getLogger(__name__)

MIGRATIONS_FOLDER = "edgedb/migrations"


class MigrationError(Exception):
    pass


def _fmt_version(version: int) -> str:
    return "[NEW]" if version == -1 else f"#{version:04}"


class Migration:
    def __init__(self, filename: str) -> None:
        self._filename = filename

        left_part, _, right_part = filename.partition("_")

        self.name = right_part.rpartition(".")[0]

        try:
            self.version = int(left_part)
        except ValueError:
            raise MigrationError(f"Bad version format in filename: {left_part}")

    async def run(self, pool: edgedb.AsyncIOPool) -> None:
        with open(f"{MIGRATIONS_FOLDER}/{self._filename}") as f:
            async with pool.acquire() as con:
                try:
                    async with con.transaction():
                        await con.execute(f.read())
                        await con.fetchall(
                            "UPDATE DB SET { schema_version := <int16>$0 }",
                            self.version,
                        )
                except Exception as e:
                    raise MigrationError(f"Error running {self}: {e}")

    def __str__(self) -> str:
        return _fmt_version(self.version)


async def migrate(app: web.Application) -> None:
    await app["edgedb_ready"].wait()

    can_fetch_database_version = await app["edgedb"].fetchone(
        """
        SELECT EXISTS (
            WITH MODULE schema
            SELECT ObjectType{name}
            filter .name = 'default::DB'
            LIMIT 1
        )
        """
    )

    if can_fetch_database_version:
        database_version = await app["edgedb"].fetchone(
            "SELECT DB.schema_version LIMIT 1"
        )
    else:
        database_version = -1

    filenames = sorted(os.listdir(MIGRATIONS_FOLDER))
    filenames = filenames[database_version + 1 :]

    if filenames:
        log.debug(
            f"applying {len(filenames)} migrations to version {_fmt_version(database_version)}"
        )
    else:
        log.debug(f"no new migrations from version {_fmt_version(database_version)}")

        return

    try:
        for filename in filenames:
            migration = Migration(filename)

            log.info(
                f"migrating {_fmt_version(database_version)} -> {migration} {migration.name}"
            )

            await migration.run(app["edgedb"])

            database_version += 1
    except MigrationError as e:
        log.fatal(f"Migration error: {e}")

        sys.exit(1)

    log.info("finished migrations")
