#!/bin/sh
# A stdio gateway per client connection, sharing the lab's profile database.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
case "${1:-}" in
  web|backend) profile="lab_$1" ;;
  *) echo 'Usage: gateway.sh web|backend [toolkit|teammate]' >&2; exit 2 ;;
esac
service=${2:-toolkit}
case "$service" in toolkit|teammate) ;; *) exit 2 ;; esac
exec docker compose --project-directory "$root" run --rm -T --no-deps "$service" \
  gateway run --profile "$profile" --cpus=1 --memory=256Mb \
  --long-lived --watch=false --log-calls=false --verify-signatures=false \
  --interceptor=before:exec:/lab/scripts/policy.sh
