#!/bin/sh
set -e

echo "Aguardando PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  sleep 1
done
echo "PostgreSQL disponível."

echo "Rodando migrations..."
python manage.py migrate --noinput

echo "Iniciando servidor Django..."
exec python manage.py runserver 0.0.0.0:8000
