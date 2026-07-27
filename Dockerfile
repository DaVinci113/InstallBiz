FROM python:3.13.3-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Устанавливаем uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Копируем файлы манифеста ПЕРВЫМИ (для кэширования слоев Docker)
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости.
# --frozen гарантирует использование uv.lock, --no-cache ускоряет сборку
RUN uv sync --frozen

# Копируем исходный код приложения
COPY . /app

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]