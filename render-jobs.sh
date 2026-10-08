#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if python3 -c 'import yaml' >/dev/null 2>&1; then
    exec python3 "$project_dir/scripts/render_jobs.py" "$@"
fi
if command -v uv >/dev/null 2>&1; then
    exec uv run --directory "$project_dir" --locked python "$project_dir/scripts/render_jobs.py" "$@"
fi
echo 'Python 3 with PyYAML, or uv, is required to render jobs.' >&2
exit 2
