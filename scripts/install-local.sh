#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(dirname -- "$SCRIPT_DIR")
SKILL_SOURCE="$REPO_DIR/skills/google-ads"
CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
SKILL_TARGET="$CODEX_SKILLS_DIR/google-ads"

uv tool install --reinstall --editable "$REPO_DIR"

mkdir -p "$CODEX_SKILLS_DIR"
if [ -L "$SKILL_TARGET" ]; then
  CURRENT_TARGET=$(readlink "$SKILL_TARGET")
  if [ "$CURRENT_TARGET" != "$SKILL_SOURCE" ]; then
    echo "Refusing to replace existing skill symlink: $SKILL_TARGET -> $CURRENT_TARGET" >&2
    exit 1
  fi
elif [ -e "$SKILL_TARGET" ]; then
  echo "Refusing to replace existing skill path: $SKILL_TARGET" >&2
  exit 1
else
  ln -s "$SKILL_SOURCE" "$SKILL_TARGET"
fi

echo "Installed gads and linked skill: $SKILL_TARGET"
