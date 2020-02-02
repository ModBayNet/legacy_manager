#!/usr/bin/python3

import sys
import pathlib
import argparse

from typing import List, Callable, Sequence

from faker import Faker
from faker.providers import internet
from faker.utils.text import slugify

fake = Faker()
fake.add_provider(internet)

SAMPLES_FOLDER = "edgedb/data/samples"

MAX_COMMENT_LEN = 200
MIN_NAME_LEN = 5
MAX_NAME_LEN = 12
MAX_BIO_LEN = 256

UNIQUE_ATTEMPTS = 5

parser = argparse.ArgumentParser(
    prog="populate_fake_data.py", description="Script for populating fake data files"
)
parser.add_argument(
    "--user-emails",
    type=int,
    help="How many user emails to generate. Defaults to 200",
    default=200,
)
parser.add_argument(
    "--user-nicknames",
    type=int,
    help="How many user nicknames to generate. Defaults to 200",
    default=200,
)
parser.add_argument(
    "--user-bios",
    type=int,
    help="How many user bios to generate. Defaults to 200",
    default=200,
)
parser.add_argument(
    "--team-names",
    type=int,
    help="How many team names to generate. Defaults to 200",
    default=200,
)
parser.add_argument(
    "--comment-bodies",
    type=int,
    help="How many comment bodies to generate. Defaults to 1000",
    default=1000,
)
parser.add_argument(
    "--overwrite", "-o", action="store_true", help="Skip file overwrite prompts",
)
parser.add_argument(
    "--wipe", "-w", action="store_true", help="Remove sample data folder and exits",
)

group = parser.add_mutually_exclusive_group()
group.add_argument(
    "--only", "-O", help="Only generate these objects (comma separated)", type=str
)
group.add_argument(
    "--skip", "-S", help="Skip generating these (comma separated)", type=str
)

args = parser.parse_args()


_GeneratorFnType = Callable[[int], Sequence[str]]


def write_to(path: str,) -> Callable[[_GeneratorFnType], Callable[[int], None]]:
    def decorator(fn: _GeneratorFnType) -> Callable[[int], None]:
        def wrapper(count: int) -> None:
            full_path = pathlib.Path(f"{SAMPLES_FOLDER}/{path}")
            if not full_path.exists():
                full_path.parent.mkdir(parents=True, exist_ok=True)

            open_mode = "w"
            if full_path.exists():
                if not args.overwrite:
                    answer = input(f"Overwrite {full_path}? (y|n): ")
                    if answer.lower() != "y":
                        open_mode = "a"

            first_line = True
            with open(full_path, open_mode) as f:
                for item in fn(count):
                    nl = "\n"
                    if first_line:
                        first_line = False
                        if open_mode == "w":
                            nl = ""

                    item = item.replace("\n", "\\n")
                    f.write(f"{nl}{item}")

        return wrapper

    return decorator


def ensure_unique(fn: _GeneratorFnType) -> _GeneratorFnType:
    f"""
    Dumb unique checker, tries to generate sample {UNIQUE_ATTEMPTS} times then gives up.
    """

    def wrapper(count: int) -> Sequence[str]:
        generated: List[str] = []
        diff = count
        for _ in range(UNIQUE_ATTEMPTS):
            generated.extend(fn(diff))

            pure = set(generated)
            diff = len(generated) - len(pure)

            generated = list(pure)

            if diff <= 0:
                break

            print(f"detected {diff} duplicates, attempting to regenerate...")

            # increase pool of values but lets not go too crazy
            # TODO: dynamic value, based on ratio of expected/duplicates?
            diff *= 2

        if diff:
            print(
                f"Failed to generate {count} unique items in {UNIQUE_ATTEMPTS} attempts."
                f"Consider using lower number"
            )
            sys.exit(1)

        assert (
            len(generated) >= count
        ), f"generator produced only {len(generated)} samples, expected {count}"

        # generated values should be sliced because diff variable is multiplied
        return generated[:count]

    return wrapper


@write_to("users/emails")
@ensure_unique
def generate_user_emails(count: int) -> Sequence[str]:
    return [fake.email() for _ in range(count)]


def _generate_names(count: int) -> Sequence[str]:
    # splitted to several lines because of black formatting
    word_list = ["super", "crazy", "cool", "epic", "gamer", "killer", "miner", "ru"]
    word_list.extend(("notso", "many", "few", "big", "small", "haha", "clown"))
    word_list.extend(("1337", "1000", "666", "9999", "80", "1111", "48", "69", "42"))
    word_list.extend(str(i) for i in range(10))

    # faker implementation does not allow length configuration
    # minimum length of fake.text is 5 which is more than MIN_NAME_LEN
    return [
        slugify(fake.text(max_nb_chars=MAX_NAME_LEN, ext_word_list=word_list))
        for _ in range(count)
    ]


@write_to("users/nicknames")
@ensure_unique
def generate_user_nicknames(count: int) -> Sequence[str]:
    return _generate_names(count)


@write_to("users/bios")
@ensure_unique
def generate_user_bios(count: int) -> Sequence[str]:
    return [fake.text(max_nb_chars=MAX_COMMENT_LEN) for _ in range(MAX_BIO_LEN)]


@write_to("teams/names")
@ensure_unique
def generate_team_names(count: int) -> Sequence[str]:
    return _generate_names(count)


@write_to("comments/bodies")
def generate_comment_bodies(count: int) -> Sequence[str]:
    locales = ("en_US", "ru_RU")

    generated: List[str] = []
    for locale in locales:
        localized_fake = Faker(locale)
        generated.extend(
            localized_fake.text(max_nb_chars=MAX_COMMENT_LEN)
            for _ in range(count // len(locales))
        )

    # TODO: figure out how to properly deal with leftovers
    leftovers = count - len(generated)
    if leftovers:
        # latest localized_fake object is used
        generated.extend(
            localized_fake.text(max_nb_chars=MAX_COMMENT_LEN) for _ in range(leftovers)
        )

    return generated


def wipe_dir() -> None:
    import shutil

    shutil.rmtree(SAMPLES_FOLDER)


def main() -> None:
    things_to_do = {
        "user_emails": {"count": args.user_emails, "fn": generate_user_emails},
        "user_nicknames": {"count": args.user_nicknames, "fn": generate_user_nicknames},
        "user_bios": {"count": args.user_bios, "fn": generate_user_bios},
        "team_names": {"count": args.team_names, "fn": generate_team_names},
        "comment_bodies": {"count": args.comment_bodies, "fn": generate_comment_bodies},
    }
    if args.skip:
        for name in args.skip.split(","):
            things_to_do.pop(name)
    elif args.only:
        things_to_do = {
            k: v for k, v in things_to_do.items() if k in args.only.split(",")
        }

    for name, property in things_to_do.items():
        print(f"generatong {property['count']:>4} {name}...")
        property["fn"](property["count"])
        print(f"done genertaing {name}")
        print()


if __name__ == "__main__":
    if args.wipe:
        wipe_dir()
    else:
        main()
