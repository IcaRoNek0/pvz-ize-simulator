#!/bin/sh
set -eu
TARGET=${1:?usage: ROLLBACK.sh TARGET_COPY}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BASELINE="$SCRIPT_DIR/BASELINE_FILE"
if [ ! -f "$BASELINE" ]; then echo "missing baseline: $BASELINE" >&2; exit 2; fi
cp "$BASELINE" "$TARGET"
