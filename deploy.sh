#!/usr/bin/env bash
# Copy a deployment's configuration to its machine and (re)start Turf Tools.
#
#   ./deploy.sh <host> <env file> [<turf-tools checkout>]
#
# <env file> is your filled-in copy of deploy/.env.example from the app repo;
# the checkout defaults to ../turf-tools. Safe to re-run: it's also how you
# apply a changed env file or new images. Steps 3 and 4 of the app repo's
# deploy/README.md, scripted.
set -euo pipefail

host="${1:?usage: ./deploy.sh <host> <env file> [<turf-tools checkout>]}"
env_file="${2:?usage: ./deploy.sh <host> <env file> [<turf-tools checkout>]}"
repo="${3:-../turf-tools}"
user="${SSH_USER:-ubuntu}"
files=(compose.yaml Caddyfile postgres-init.sql backup.sh)

for f in "${files[@]}"; do
  [[ -f "$repo/deploy/$f" ]] || { echo "no $repo/deploy/$f; pass the checkout path" >&2; exit 1; }
done
[[ -f "$env_file" ]] || { echo "no env file at $env_file" >&2; exit 1; }

echo "==> copying configuration to $host"
sources=()
for f in "${files[@]}"; do sources+=("$repo/deploy/$f"); done
scp -q "${sources[@]}" "$user@$host:/tmp/"
scp -q "$env_file" "$user@$host:/tmp/turf-tools.env"

# The directory is root-only, so files are staged in /tmp and installed with
# sudo. .env stays private; the rest must be world-readable, because Postgres
# runs as a non-root user and silently skips an init script it can't read.
ssh "$user@$host" "
  set -e
  sudo install -d -m 0750 /etc/turf-tools
  cd /tmp
  sudo install -m 0644 -o root -g root ${files[*]} /etc/turf-tools/
  sudo install -m 0640 -o root -g root turf-tools.env /etc/turf-tools/.env
  rm -f ${files[*]} turf-tools.env
  cd /etc/turf-tools
  sudo docker compose pull --quiet
  sudo docker compose up -d --remove-orphans
  sudo docker compose ps
"
echo "==> done: https://$(grep -E '^DOMAIN=' "$env_file" | cut -d= -f2)"
