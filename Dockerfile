# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/go/dockerfile-reference/

# Want to help us make this template better? Share your feedback here: https://forms.gle/ybq9Krt8jtBL3iCk7

ARG PYTHON_VERSION=3.11.3
FROM python:${PYTHON_VERSION}-slim as base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds.
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install -r requirements.txt

# Switch to the non-privileged user to run the application.
USER appuser

# Copy the source code into the container.
COPY . .

# Set environment variables
ARG DISCORD_TOKEN
ARG OLLAMA_URL
ARG OLLAMA_MODEL
ARG STABLE_DIFFUSION_URL
ARG WAKE_WORDS
ARG HISTORY_LIMIT
ARG RESPONSE_TIME
ARG POSITIVE_PROMPT
ARG NEGATIVE_PROMPT
ARG STYLES

ENV DISCORD_TOKEN=${DISCORD_TOKEN}
ENV OLLAMA_URL=${OLLAMA_URL}
ENV OLLAMA_MODEL=${OLLAMA_MODEL}
ENV STABLE_DIFFUSION_URL=${STABLE_DIFFUSION_URL}
ENV WAKE_WORDS=${WAKE_WORDS}
ENV HISTORY_LIMIT=${HISTORY_LIMIT}
ENV RESPONSE_TIME=${RESPONSE_TIME}
ENV POSITIVE_PROMPT=${POSITIVE_PROMPT}
ENV NEGATIVE_PROMPT=${NEGATIVE_PROMPT}
ENV STYLES=${STYLES}

# Run the application.
CMD ["python", "main.py"]
