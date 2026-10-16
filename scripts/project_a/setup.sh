#!/usr/bin/env bash
# Safe, rerunnable setup for the published Cloud environment; never use root Compose.
set -euo pipefail
cd "$(dirname "$0")/../.."
git submodule update --init --recursive
if git submodule status --recursive | grep -Eq '^[+U-]'; then
  echo 'Missing or mismatched submodule; refusing floating source.' >&2
  exit 1
fi
# Always address the local managed daemon, never an inherited remote context.
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker --host=unix:///var/run/docker.sock info --format '{{.ServerVersion}}'
docker --host=unix:///var/run/docker.sock build \
  --secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -f scripts/project_a/Dockerfile -t project-a-humble:w0 .
