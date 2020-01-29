import argparse

argparser = argparse.ArgumentParser(
    prog="mb_manager", description="ModBay manager instance"
)
argparser.add_argument(
    "--verbosity",
    "-v",
    choices=["critical", "error", "warning", "info", "debug"],
    default="info",
    help="Verbosity level",
)
argparser.add_argument(
    "--populate-db",
    action="store_true",
    help="Populate database with sample data and exit",
)

args = argparser.parse_args()
