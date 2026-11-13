#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
while read -r directory url commit; do
  [[ -z "$directory" || "$directory" == \#* ]] && continue
  if [[ ! -e "$directory" ]]; then
    mkdir -p -- "$(dirname -- "$directory")"
    # Stage the checkout before placing it at its final path.
    checkout=$(mktemp -d)
    git init -q "$checkout"
    git -C "$checkout" remote add origin "$url"
    git -C "$checkout" fetch --depth 1 origin "$commit"
    git -C "$checkout" checkout --quiet --detach FETCH_HEAD
    mv -- "$checkout" "$directory"
  fi
  actual=$(git -C "$directory" rev-parse HEAD)
  [[ "$actual" == "$commit" ]] || {
    echo "$directory is at $actual. Expected $commit. Use a clean checkout to build." >&2
    exit 1
  }
done < sources.lock

git -C src/gaussian-splatting submodule update --init --recursive -- \
  submodules/simple-knn submodules/diff-gaussian-rasterization submodules/fused-ssim

for module in fast-livo2-rtk gaussian-splatting; do
  case "$module" in
    fast-livo2-rtk) source=src/FAST-LIVO2-RTK ;;
    gaussian-splatting) source=src/gaussian-splatting ;;
  esac
  patch=$PWD/patches/$module.patch
  if git -C "$source" apply --reverse --check "$patch" 2>/dev/null; then
    continue
  fi
  git -C "$source" apply "$patch"
done
