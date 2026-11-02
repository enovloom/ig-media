#!/usr/bin/env bash
# Decrypts an insights bundle made by cloud/insights.sh.
#   bash brain/tools/decrypt.sh <private key.pem> <output dir> [insights/history/YYYY-MM-DD]
# Without the third argument it opens insights/latest.
set -euo pipefail
key=$1; dst=$2; base=${3:-insights/latest}
mkdir -p "$dst"
pass=$(openssl pkeyutl -decrypt -inkey "$key" -pkeyopt rsa_padding_mode:oaep -in "$base.key")
openssl enc -d -aes-256-cbc -pbkdf2 -in "$base.enc" -pass "pass:$pass" | tar xzf - -C "$dst"
jq -r '"fetched \(.fetchedAt)  calls=\(.calls) errors=\(.errors)"' "$dst/meta.json"
