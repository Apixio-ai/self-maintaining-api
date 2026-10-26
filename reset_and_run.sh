#!/bin/bash
# Reset the sample repo to master and re-run the demo from a clean state.
# Works both ways:
#  - in the original demo folder, where sample_repo is already a git repo
#  - in a fresh GitHub clone, where sample_repo is just files (no .git
#    folder, because git does not push .git folders). In that case we
#    initialise it once, with the old-code files as the baseline commit.
set -e
cd "$(dirname "$0")/sample_repo"
if [ ! -d .git ]; then
  git init -b master -q
  git add -A
  git -c user.name="demo" -c user.email="demo@example.com" commit -qm "baseline: old Stripe meter usage fields"
fi
git checkout master -q
git branch -D fix/stripe-meter-usage-2025-09-30 -q 2>/dev/null || true
git branch -D fix/stripe-receipt-email-rename -q 2>/dev/null || true
git checkout -- . 2>/dev/null || true
rm -rf __pycache__
cd ..
python3 maintainer.py \
  --old specs/spec_old.json \
  --new specs/spec_new.json \
  --repo sample_repo \
  --branch fix/stripe-meter-usage-2025-09-30
