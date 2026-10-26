#!/bin/bash
# Reset the sample repo to master and re-run the demo from a clean state.
set -e
cd "$(dirname "$0")/sample_repo"
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
