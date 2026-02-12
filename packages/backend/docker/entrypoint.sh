#!/bin/bash
set -e

# Ensure passport directory exists (volume mount point)
mkdir -p /app/storage/passport

# Symlink passport keys from persistent volume to expected location
ln -sf /app/storage/passport/oauth-private.key /app/storage/oauth-private.key 2>/dev/null || true
ln -sf /app/storage/passport/oauth-public.key /app/storage/oauth-public.key 2>/dev/null || true

# If command arguments are passed (e.g. queue-worker, scheduler), skip full setup
if [ $# -gt 0 ]; then
  exec "$@"
fi

# ---- Full setup (backend only) ----

# Wait for database to be ready
echo "Waiting for database..."
until php artisan db:monitor --databases=pgsql 2>/dev/null; do
  sleep 2
done
echo "Database is ready."

# Run migrations
php artisan migrate --force --no-interaction 2>/dev/null || true

# Generate Passport keys if they don't exist in the persistent volume
if [ ! -f /app/storage/passport/oauth-private.key ] || [ ! -f /app/storage/passport/oauth-public.key ]; then
  echo "Generating Passport keys in persistent volume..."
  php artisan passport:keys --force --no-interaction
  # Move keys to persistent volume
  mv /app/storage/oauth-private.key /app/storage/passport/oauth-private.key 2>/dev/null || true
  mv /app/storage/oauth-public.key /app/storage/passport/oauth-public.key 2>/dev/null || true
  # Fix ownership so www-data can read them
  chown www-data:www-data /app/storage/passport/oauth-private.key /app/storage/passport/oauth-public.key 2>/dev/null || true
  chmod 644 /app/storage/passport/oauth-private.key /app/storage/passport/oauth-public.key 2>/dev/null || true
  # Re-create symlinks
  ln -sf /app/storage/passport/oauth-private.key /app/storage/oauth-private.key
  ln -sf /app/storage/passport/oauth-public.key /app/storage/oauth-public.key
  echo "Passport keys generated and persisted."
fi

# Ensure correct permissions (www-data must be able to read the keys)
chown www-data:www-data /app/storage/passport/oauth-private.key /app/storage/passport/oauth-public.key 2>/dev/null || true
chmod 644 /app/storage/passport/oauth-private.key /app/storage/passport/oauth-public.key 2>/dev/null || true

# Create personal access client if none exists
CLIENT_EXISTS=$(php artisan tinker --execute="echo \Illuminate\Support\Facades\DB::table('oauth_personal_access_clients')->count();" 2>/dev/null || echo "0")
if [ "$CLIENT_EXISTS" = "0" ] || [ -z "$CLIENT_EXISTS" ]; then
  echo "Creating Passport personal access client..."
  php artisan passport:client --personal --name=FormBot --no-interaction 2>/dev/null || true
  echo "Personal access client created."
fi

# Clear caches
php artisan config:clear 2>/dev/null || true
php artisan route:clear 2>/dev/null || true

echo "Starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
