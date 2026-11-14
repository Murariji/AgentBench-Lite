#!/bin/sh
# Container start-up for the API image (Phase 11.2). Runs as root for a moment, ONLY to decide which normal
# user the server runs as; then it hands over with setpriv and never runs as root again.
#
# Why: a folder shared with -v keeps its owner's numeric id. On Linux your user is usually 1000, so a
# server running as 10001 could not write results.db there. Docker Desktop (Windows/macOS) shows shared
# folders as owned by root with full permissions, so there the default user works.
#
#   data/ owned by a normal user  -> run as that user: new files belong to YOU on your computer
#   data/ owned by root           -> run as agentbench (10001); if it cannot write there and the folder is
#                                    EMPTY (Docker just created it), make it agentbench's. Never touch a
#                                    folder that already holds files.
set -eu

DATA=/app/data
RESULTS=/app/results
DEFAULT_UID=10001
DEFAULT_GID=10001

if [ "$(id -u)" != "0" ]; then          # started with --user: nothing to decide
    exec python scripts/serve_api.py "$@"
fi

owner_uid=$(stat -c %u "$DATA")
owner_gid=$(stat -c %g "$DATA")
if [ "$owner_uid" != "0" ]; then
    run_uid=$owner_uid
    run_gid=$owner_gid
else
    run_uid=$DEFAULT_UID
    run_gid=$DEFAULT_GID
fi

for dir in "$DATA" "$RESULTS"; do
    if ! setpriv --reuid="$run_uid" --regid="$run_gid" --clear-groups test -w "$dir"; then
        if [ -z "$(ls -A "$dir")" ]; then
            chown "$run_uid:$run_gid" "$dir"
        else
            echo "Not starting: the server (user $run_uid) cannot write to $dir, and it already holds files," >&2
            echo "so it is left untouched. Make it writable for that user, or run with --user <uid>:<gid>." >&2
            exit 1
        fi
    fi
done

export HOME=/tmp                        # the chosen user may have no home folder in the image
exec setpriv --reuid="$run_uid" --regid="$run_gid" --clear-groups python scripts/serve_api.py "$@"
