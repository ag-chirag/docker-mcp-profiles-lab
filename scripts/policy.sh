#!/bin/sh
# Docker sends the tools/call request on stdin. Empty stdout allows the call;
# a CallToolResult on stdout replaces it. Diagnostics belong on stderr.
set -eu
request=$(cat)
name=$(printf '%s' "$request" | jq -er '(.Params // .params).name | select(type == "string")')
environment=$(printf '%s' "$request" | jq -r '(.Params // .params).arguments.environment // ""')
if [ "$name" = "release_preview" ] && [ "$environment" = "production" ]; then
  printf '%s\n' 'policy: blocked production release preview' >&2
  printf '%s\n' '{"isError":true,"content":[{"type":"text","text":"Lab policy: production release previews require a separate approval."}]}'
else
  printf 'policy: allowed %s\n' "$name" >&2
fi
