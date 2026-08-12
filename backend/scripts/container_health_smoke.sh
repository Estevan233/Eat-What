#!/bin/sh
set -eu

image="${1:-eat-what-api:test}"
name="eat-what-health-smoke-$$"

cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker run -d --name "$name" -p 127.0.0.1::8080 \
  -e ENVIRONMENT=prod \
  -e DEBUG=false \
  -e JWT_SECRET=container-health-smoke-secret-32chars \
  -e WX_APPID=wx-container-smoke \
  -e CLOUDBASE_ENV_ID=cloud-container-smoke \
  "$image" >/dev/null

port="$(docker port "$name" 8080/tcp | sed 's/.*://')"
attempt=0
until curl --fail --silent "http://127.0.0.1:${port}/health" >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    docker logs "$name"
    exit 1
  fi
  sleep 1
done

curl --fail --silent "http://127.0.0.1:${port}/health"
