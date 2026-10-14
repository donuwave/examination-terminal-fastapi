#!/bin/sh
# Ключи для подписи JWT. В репозиторий не попадают (папка certs в .gitignore).
set -e
mkdir -p certs
if [ -f certs/jwt-private.pem ]; then
  echo "Ключи уже есть: certs/jwt-private.pem. Удалите их, если нужно создать заново (все токены станут недействительны)."
  exit 0
fi
openssl genrsa -out certs/jwt-private.pem 2048
openssl rsa -in certs/jwt-private.pem -pubout -out certs/jwt-public.pem
chmod 600 certs/jwt-private.pem
echo "Готово: certs/jwt-private.pem и certs/jwt-public.pem"
