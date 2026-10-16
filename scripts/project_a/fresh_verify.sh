#!/usr/bin/env bash
# Freeze an exact committed candidate; never test a copied mutable working tree as a release.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ "$#" -ne 2 ] || [[ ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Usage: fresh_verify.sh exact-candidate-sha fresh-output-directory' >&2
  exit 2
fi
candidate=$1
destination=$(realpath -m "$2")
repository=$(pwd)
if [ -e "$destination" ] || [ -L "$destination" ]; then
  echo 'Fresh verification requires an absent destination.' >&2
  exit 1
fi
git cat-file -e "$candidate^{commit}"
mkdir -p "$destination"
trap 'fresh_rc=$?; printf "%s\n" "$fresh_rc" > "$destination/fresh-exit-code.txt"' EXIT
printf '%s\n' "$candidate" > "$destination/candidate.txt"
git clone --no-hardlinks --no-checkout "$repository" "$destination/checkout"
git -C "$destination/checkout" checkout --detach "$candidate"
git -C "$destination/checkout" submodule update --init --recursive
check_candidate() {
  if [ "$(git -C "$destination/checkout" rev-parse HEAD)" != "$candidate" ] || \
     [ -n "$(git -C "$destination/checkout" status --porcelain)" ]; then
    echo 'Candidate checkout is not exact and clean.' >&2
    exit 1
  fi
}
check_candidate
cd "$destination/checkout"
scripts/project_a/setup.sh 2>&1 | tee "$destination/setup.log"
check_candidate
scripts/project_a/verify.sh all "$destination/verification"
check_candidate
