FROM python:3.12-slim

WORKDIR /app

# installing uv into the docker container
RUN pip install uv

# installing necessary dependency for lightgbm that isn't included in 3.12-slim
RUN apt-get update && apt-get install -y libgomp1 && rm -rf /var/lib/apt/lists/*

# dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# relevant code files
COPY service/ service/
COPY features/feature_engineering.py features/
COPY modeling/shap_analysis.py modeling/
COPY modeling/models/lgbm_tuned.txt modeling/models/
COPY modeling/models/lgbm_tuned.json modeling/models/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
