#!/bin/bash
# Read-only parameter/file gate. This never submits or grants scientific approval.
# Usage: bash validate_before_submit.sh JOB_DIR [auto|equil|production] [--cmd-input CMD_MDIN]
# Bind --cmd-input or --reference-equil (or corresponding LIGAMD3_* environment variable).
# Without either source mode, require JOB_DIR/cmd-source.mdin; no unverified fallback.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 JOB_DIR [auto|equil|production] [--cmd-input CMD_MDIN]" >&2
    exit 2
fi
# Unconditional: malformed/absent/wrong igamd must never skip the guard.
# exec preserves nonzero exit for missing Python/checker and every failed check.
exec python3 "${SCRIPT_DIR}/check_ligamd3_tutorial_params.py" "$@" --submission
