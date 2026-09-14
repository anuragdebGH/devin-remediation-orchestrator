#!/usr/bin/env bash
set -euo pipefail

repository="${GITHUB_REPOSITORY:-anuragdebGH/superset}"
label="${TRIGGER_LABEL:-devin-remediate}"

for issue in 1 3; do
  state="$(gh issue view "$issue" --repo "$repository" --json state --jq .state)"
  if [[ "$state" != "OPEN" ]]; then
    echo "Expected $repository#$issue to be OPEN, found $state" >&2
    exit 1
  fi
done

label_count="$(
  gh label list --repo "$repository" --limit 100 --json name \
    --jq "[.[] | select(.name == \"$label\")] | length"
)"
if [[ "$label_count" != "1" ]]; then
  echo "Expected label '$label' in $repository" >&2
  exit 1
fi

echo "Verified $repository issues #1 and #3 and trigger label '$label'."
echo "Do not apply the trigger label until the live webhook is ready."
