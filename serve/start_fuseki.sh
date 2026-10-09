#!/usr/bin/env bash
# Khởi động Fuseki với cấu hình của project.
# Cần: Java 17+ và Apache Jena Fuseki (xem README.md).
#   FUSEKI_HOME=/đường/dẫn/apache-jena-fuseki-X.Y.Z bash start_fuseki.sh
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v java >/dev/null; then
  echo "Chưa có Java. Cài Java 17 trở lên (ví dụ: brew install openjdk@21)"; exit 1
fi
if command -v fuseki-server >/dev/null; then
  exec fuseki-server --config=config.ttl
elif [ -n "${FUSEKI_HOME:-}" ] && [ -x "$FUSEKI_HOME/fuseki-server" ]; then
  exec "$FUSEKI_HOME/fuseki-server" --config=config.ttl
else
  echo "Không tìm thấy fuseki-server. Đặt FUSEKI_HOME tới thư mục Fuseki đã giải nén."; exit 1
fi
