#!/bin/sh

# Description:
#     This script creates migration file copying current schema to it.
#
# Usage:
#     scripts/make_migration.sh <name>
#
# Example:
#     scripts/make_migration.sh set_username_regex

set -e

EDGEDB_FOLDER='edgedb'
MIGRATIONS_FOLDER="$EDGEDB_FOLDER/migrations"
SCHEMA_FILE="$EDGEDB_FOLDER/schema.esdl"

VERSION_NUMBER_DIGITS=4

if [ "$#" -ne 1 ]; then
  echo "Please provide migration name in first argument" >&2
  exit 1
fi

migration_name=$1

schema_modified=0
git diff-index --quiet HEAD "$SCHEMA_FILE" || schema_modified=$?
if [ $schema_modified -eq 0 ]; then
  read -r -p "Schema file $SCHEMA_FILE was not modified, continue? (y|n): " answer
  case "$answer" in
    [^yY])
        echo "Exiting"
        exit 0
        ;;
  esac
fi

latest_migration_file=$(find "$MIGRATIONS_FOLDER" -maxdepth 1 -type f -name '*.edgeql' -printf "%f\n" | sort | tail -n 1)
next_version=$(printf "%0${VERSION_NUMBER_DIGITS}d" $((10#${latest_migration_file:0:$VERSION_NUMBER_DIGITS} + 1)))
new_file_name="$MIGRATIONS_FOLDER/${next_version}_${migration_name}.edgeql"

cat << EOF > "$new_file_name"
### SCHEMA MIGRATION START ###
CREATE MIGRATION $migration_name TO {
$(awk '{printf("    %s\n", $0)}' "$SCHEMA_FILE")
};

COMMIT MIGRATION $migration_name;
### SCHEMA MIGRATION END ###
EOF

printf "Successfully created %s" "$new_file_name"
