FROM python:3.12-slim

# Install system dependencies for Playwright (including fonts)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-unifont \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (chromium only, skip system deps since we installed them above)
RUN playwright install chromium

# Copy application
COPY . .

# Create directories
RUN mkdir -p /app/screenshots /app/uploads

EXPOSE 9000 6080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
