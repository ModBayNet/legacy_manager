from __future__ import annotations

import os
import sys
import uuid
import random
import logging

from typing import Any, Dict, List, Optional, Sequence
from dataclasses import dataclass

import edgedb

from mb_backend.config import Config
from mb_backend.security import _make_hash

log = logging.getLogger(__name__)

SAMPLES_FOLDER = "edgedb/data/samples"

TOTAL_ARTICLES = 200
TOTAL_COMMENTS = 400
TOTAL_USERS = 200
TOTAL_TEAMS = 20

COMMET_BODIES_FILE = f"{SAMPLES_FOLDER}/comments/bodies"
USER_EMAILS_FILE = f"{SAMPLES_FOLDER}/users/emails"
USER_NICKNAMES_FILE = f"{SAMPLES_FOLDER}/users/nicknames"
USER_BIOS_FILE = f"{SAMPLES_FOLDER}/users/bios"
TEAM_NAMES_FILE = f"{SAMPLES_FOLDER}/teams/names"


@dataclass
class User:
    nickname: str
    email: str
    email_verified: bool
    avatar: str
    password: bytes
    bio: str


@dataclass
class Team:
    name: str
    avatar: str
    members: List[User]


@dataclass
class Article:
    author: User
    team: Optional[Team]
    rating: int
    state: str
    language: str

    # required for hashing
    index__: int

    def __hash__(self) -> int:
        return hash(self.index__)


@dataclass
class Comment:
    author: User
    article: Article
    parent: Optional[Comment]
    rating: int
    body: str
    deleted: bool


users = []
teams = []
articles = []
comments: List[Comment] = []

article_to_comments_map: Dict[Article, List[Comment]] = {}

articles_by_id = {}
comments_by_id = {}


def populate_db(config: Config) -> None:
    if not os.path.exists(SAMPLES_FOLDER):
        log.fatal(
            f"{SAMPLES_FOLDER} folder does not exist. Use scripts/populate_fake_data.py"
        )
        log.fatal("Note: sample files are not included into docker image by default")
        log.fatal("Use volume to mount them: -v $PWD/edgedb/data:/code/edgedb/data")

        sys.exit(1)

    con = None
    try:
        log.info("connecting to edgedb")
        con = edgedb.connect(**config["edgedb"])
        _populate(con)
    finally:
        if con is not None:
            log.info("closing edgedb connection")
            con.close()


def _read_lines(filename: str) -> Sequence[str]:
    with open(filename, "r") as f:
        return f.read().splitlines()


def _choose_random_items(
    collection: Sequence[Any], count: int, unique: bool = False
) -> Sequence[Any]:
    if not unique:
        return random.choices(collection, k=count)

    if count > len(collection):
        raise ValueError(
            f"Not enough samples in collection to pick {count} random items"
        )

    return random.sample(collection, count)


def _populate(con: edgedb.BlockingIOConnection) -> None:
    _populate_users(con)
    _populate_teams(con)
    _populate_articles(con)
    _populate_comments(con)

    _assign_teams_to_articles()
    _assign_users_to_teams()
    _assign_comments_to_articles()

    # TODO: find a way to optimize these with bulk inserts
    _insert_users(con)
    _insert_teams(con)
    _insert_articles(con)
    _insert_comments(con)

    _update_comment_parents(con)


def _populate_users(con: edgedb.BlockingIOConnection) -> None:
    available_nicknames = _read_lines(USER_NICKNAMES_FILE)
    available_emails = _read_lines(USER_EMAILS_FILE)
    available_bios = _read_lines(USER_BIOS_FILE)

    nicknames = _choose_random_items(available_nicknames, TOTAL_USERS, unique=True)
    emails = _choose_random_items(available_emails, TOTAL_USERS, unique=True)
    bios = _choose_random_items(available_bios, TOTAL_USERS)

    for i in range(TOTAL_USERS):
        users.append(
            User(
                nickname=nicknames[i],
                email=emails[i],
                email_verified=True,
                avatar="/dev/null",
                password=_make_hash(nicknames[i]),
                bio=bios[i],
            )
        )


def _populate_teams(con: edgedb.BlockingIOConnection) -> None:
    available_names = _read_lines(TEAM_NAMES_FILE)

    names = _choose_random_items(available_names, TOTAL_TEAMS, unique=True)

    for i in range(TOTAL_TEAMS):
        teams.append(Team(name=names[i], avatar="/dev/null", members=[]))


def _populate_articles(con: edgedb.BlockingIOConnection) -> None:
    for i in range(TOTAL_ARTICLES):
        articles.append(
            Article(
                author=random.choice(users),
                team=None,
                rating=random.randrange(-10, 10),
                state=random.choice(("draft", "hidden", "published")),
                language=random.choice(("en", "ru")),
                index__=i,
            )
        )


def _populate_comments(con: edgedb.BlockingIOConnection) -> None:
    available_bodies = _read_lines(COMMET_BODIES_FILE)

    bodies = _choose_random_items(available_bodies, TOTAL_COMMENTS)

    for i in range(TOTAL_COMMENTS):
        comments.append(
            Comment(
                author=random.choice(users),
                article=random.choice(articles),
                parent=None,
                rating=random.randrange(-100, 100),
                body=bodies[i],
                deleted=random.random() > 0.5,
            )
        )


def _assign_teams_to_articles() -> None:
    """Sets random team for half of articles."""

    for article in articles[: len(articles) // 2]:
        article.team = random.choice(teams)


def _assign_users_to_teams() -> None:
    """Adds users to random teams with 50% chance."""

    for user in users:
        if random.random() > 0.5:
            random.choice(teams).members.append(user)


def _assign_comments_to_articles() -> None:
    """
    Assigns random article to comments, with 70% chance adds random comment from article
    as parent.
    """

    for comment in comments:
        article = random.choice(articles)
        comment.article = article

        if article in article_to_comments_map:
            if random.random() > 0.3:
                comment.parent = random.choice(article_to_comments_map[article])

            article_to_comments_map[article].append(comment)
        else:
            article_to_comments_map[article] = [comment]


def _insert_users(con: edgedb.BlockingIOConnection) -> None:
    log.info("inserting users")

    for user in users:
        con.fetchone(
            """
            INSERT User {
                nickname := <str>$nickname,
                email := <str>$email,
                email_verified := <bool>$email_verified,
                avatar := <str>$avatar,
                password := <bytes>$password,
                bio := <str>$bio,
            }
            """,
            nickname=user.nickname,
            email=user.email,
            email_verified=user.email_verified,
            avatar=user.avatar,
            password=user.password,
            bio=user.bio,
        )


def _insert_teams(con: edgedb.BlockingIOConnection) -> None:
    log.info("inserting teams")

    for team in teams:
        con.fetchone(
            """
            INSERT Team {
                name := <str>$name,
                avatar := <str>$avatar,
                members := (
                    FOR nickname IN {array_unpack(<array<str>>$members)}
                    UNION {
                        (
                            SELECT User
                            FILTER str_lower(.nickname) = nickname
                        )
                    }
                ),
            }
            """,
            name=team.name,
            avatar=team.avatar,
            members=[m.nickname.lower() for m in team.members],
        )


def _insert_articles(con: edgedb.BlockingIOConnection) -> None:
    log.info("inserting articles")

    for article in articles:
        article_id = con.fetchone(
            """
            INSERT Article {
                author := (
                    SELECT User
                    FILTER str_lower(.nickname) = <str>$author_nickname
                    LIMIT 1
                ),
                team := (
                    SELECT Team
                    FILTER str_lower(.name) = <str>$team_name
                    LIMIT 1
                ),
                rating := <int16>$rating,
                state := <str>$state,
                language := <str>$language,
            }
            """,
            author_nickname=article.author.nickname.lower(),
            team_name=article.team.name if article.team else "",
            rating=article.rating,
            state=article.state,
            language=article.language,
        )


def _insert_comments(con: edgedb.BlockingIOConnection) -> None:
    log.info("inserting comments")

    for comment in comments:
        comment_id = con.fetchone(
            """
            INSERT Comment {
                author := (
                    SELECT User
                    FILTER str_lower(.nickname) = <str>$author_nickname
                    LIMIT 1
                ),
                article := (
                    SELECT Article
                    FILTER .id = <str>$article_id
                    LIMIT 1
                ),
                rating := <int16>$rating,
                body := <str>$body,
                deleted := <bool>$deleted,
            }
            """
        )
        comments_by_id[comment_id] = comment


def _update_comment_parents(con: edgedb.BlockingIOConnection) -> None:

    # def update(comment: Comment) -> None:
    #     if
    # TODO
    pass
