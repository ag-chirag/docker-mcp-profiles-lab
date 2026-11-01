FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY servers/server.py .
ARG ROLE
ENV LAB_ROLE=${ROLE} PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
LABEL io.github.mcp-profiles-lab.component="tool-server"
USER 10001:10001
ENTRYPOINT ["python", "/app/server.py"]
