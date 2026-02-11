FROM php:8.3-fpm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    libpng-dev \
    libonig-dev \
    libxml2-dev \
    libpq-dev \
    zip \
    unzip \
    nginx \
    supervisor \
    && docker-php-ext-install pdo pdo_pgsql pgsql mbstring exif pcntl bcmath gd \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /app

# Copy composer files first for better caching
COPY composer.json ./

# Install dependencies (allow plugins, skip scripts that need the full app)
RUN composer install --optimize-autoloader --no-dev --no-scripts --no-interaction 2>/dev/null || \
    composer install --no-dev --no-scripts --no-interaction 2>/dev/null || true

# Copy the rest of the application
COPY . .

# Run post-install scripts
RUN composer dump-autoload --optimize 2>/dev/null || true

# Create storage directories
RUN mkdir -p storage/framework/{cache,sessions,views} \
    && mkdir -p storage/app/screenshots \
    && mkdir -p storage/app/uploads \
    && mkdir -p storage/logs \
    && mkdir -p bootstrap/cache \
    && chmod -R 775 storage bootstrap/cache \
    && chown -R www-data:www-data storage bootstrap/cache

# Nginx configuration
RUN rm /etc/nginx/sites-enabled/default
COPY docker/nginx.conf /etc/nginx/sites-enabled/default

# Supervisor configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Entrypoint script (handles migrations, Passport keys, etc.)
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

# PHP-FPM listens on 127.0.0.1:9000 by default, nginx connects to that

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
