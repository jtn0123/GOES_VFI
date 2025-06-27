# GOES_VFI Docker Container
FROM python:3.13-slim

LABEL maintainer="GOES_VFI Contributors"
LABEL description="GOES Video Frame Interpolation - Satellite Data Processing"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Qt6 and GUI dependencies
    libgl1-mesa-glx \
    libegl1-mesa \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxrandr2 \
    libxss1 \
    libgconf-2-4 \
    libxtst6 \
    libxext6 \
    libxi6 \
    libnss3-dev \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxss1 \
    libgtk-3-0 \
    # FFmpeg for video processing
    ffmpeg \
    # Build tools and libraries
    build-essential \
    git \
    curl \
    # Image processing libraries
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    # NetCDF and scientific computing
    libnetcdf-dev \
    libhdf5-dev \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd --create-home --shell /bin/bash app

# Set work directory
WORKDIR /app

# Copy project files first for better caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Reinstall in editable mode with all dependencies
RUN pip install -e .[test,dev]

# Create necessary directories
RUN mkdir -p /app/data /app/output /app/logs \
    && chown -R app:app /app

# Switch to application user
USER app

# Set up environment
ENV DISPLAY=:99 \
    XDG_RUNTIME_DIR=/tmp/runtime-app \
    GOES_VFI_DATA_DIR=/app/data \
    GOES_VFI_OUTPUT_DIR=/app/output \
    GOES_VFI_LOG_DIR=/app/logs

# Create runtime directory
RUN mkdir -p $XDG_RUNTIME_DIR && chmod 700 $XDG_RUNTIME_DIR

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import goesvfi; print('GOES_VFI is healthy')" || exit 1

# Expose port for web interface (if implemented)
EXPOSE 8080

# Default command (can be overridden)
CMD ["python", "-m", "goesvfi.gui", "--debug"]

# Additional labels for metadata
LABEL org.opencontainers.image.title="GOES_VFI" \
      org.opencontainers.image.description="Video Frame Interpolation for GOES Satellite Data" \
      org.opencontainers.image.url="https://github.com/username/GOES_VFI" \
      org.opencontainers.image.source="https://github.com/username/GOES_VFI" \
      org.opencontainers.image.vendor="GOES_VFI Contributors" \
      org.opencontainers.image.licenses="MIT"
