# Minimal image exposing the `norma` CLI. Build: docker build -t norma .
# Run:  docker run --rm -v "$PWD:/data" norma analyze /data/file.csv
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[lake,baselines]"
ENTRYPOINT ["norma"]
CMD ["--help"]
