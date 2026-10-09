#!/usr/bin/env bash
# Install the agentic SDLC kit into a project and configure it.
#   ~/code/agentic-sdlc-kit/install.sh [project-dir] [--yes]
# Without project-dir it asks for one (default: the current directory); --yes accepts every default.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required: the installer and the kit's lock hook use it." >&2
  exit 1
fi
exec python3 "$KIT/tools/install.py" "$@"
