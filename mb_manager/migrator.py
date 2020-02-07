import os
import sys
import logging

import edgedb

from aiohttp import web

from .config import Config

log = logging.getLogger(__name__)

MIGRATIONS_FOLDER = "edgedb/migrations"


class MigrationError(Exception):
    pass


def _fmt_db_version(version: int) -> str:
    return "[NEW]" if version == -1 else f"#{version:04}"


class EdgeDBMigration:
    def __init__(self, filename: str) -> None:
        self._filename = filename

        left_part, _, right_part = filename.partition("_")

        self.name = right_part.rpartition(".")[0]

        try:
            self.version = int(left_part)
        except ValueError:
            raise MigrationError(f"Bad version format in filename: {left_part}")

    def run(self, conn: edgedb.BlockingIOConnection) -> None:
        with open(f"{MIGRATIONS_FOLDER}/{self._filename}") as f:
            try:
                with conn.transaction():
                    conn.execute(f.read())
                    conn.fetchall(
                        "UPDATE DB SET { schema_version := <int16>$0 }", self.version,
                    )
            except Exception as e:
                raise MigrationError(f"Error running {self}: {e}")

    def __str__(self) -> str:
        return _fmt_db_version(self.version)


def _migrate_edgedb(config: Config) -> None:
    conn = edgedb.connect(**config["edgedb"])

    can_fetch_database_version = conn.fetchone(
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
        database_version = conn.fetchone("SELECT DB.schema_version LIMIT 1")
    else:
        database_version = -1

    filenames = sorted(os.listdir(MIGRATIONS_FOLDER))
    filenames = filenames[database_version + 1 :]

    if filenames:
        log.debug(
            f"applying {len(filenames)} migrations to version {_fmt_db_version(database_version)}"
        )
    else:
        log.debug(f"no new migrations from version {_fmt_db_version(database_version)}")

        return

    try:
        for filename in filenames:
            migration = EdgeDBMigration(filename)

            log.info(
                f"migrating {_fmt_db_version(database_version)} -> {migration} {migration.name}"
            )

            migration.run(conn)

            database_version += 1
    except MigrationError as e:
        log.fatal(f"Migration error: {e}")

        sys.exit(1)

    log.info("finished migrations")


def migrate(config: Config) -> None:
    _migrate_edgedb(config)
