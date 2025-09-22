#!/usr/bin/env bash
REMOTE="$1"
BRANCH="${2:-main}"
if [ -z "$REMOTE" ]; then echo "Usage: $0 \"https://<PAT>@github.com/USER/REPO.git\" [branch]"; exit 1; fi
git init
git add -A
git commit -m "Initial full ICT charting panel commit"
git branch -M "$BRANCH"
git remote add origin "$REMOTE"
git push -u origin "$BRANCH" --force
