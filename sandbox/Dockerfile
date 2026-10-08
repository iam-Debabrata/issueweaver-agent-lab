FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.4.2
RUN useradd -m -u 10001 sandbox
USER sandbox
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
