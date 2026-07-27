#!/bin/bash
# The agent's checkpointer owns the schema of whatever database it is pointed
# at, so it gets its own rather than sharing the Issue API's. Postgres runs
# everything in this directory once, when the data volume is first initialised.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE DATABASE \"${AGENT_DB_NAME:-agent_state}\";"
