# Runs env/ (generate + capture + check) and runner/ (models + scoring).
# NOT TESTED in the build sandbox (no Docker there). Pin the tag to the playwright version you use;
# the env was developed with playwright 1.63.0.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

# Same fonts as the dev machine, so screenshots match: Inter (UI), DejaVu (images, P7 theme), emoji.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-inter fonts-dejavu-core fonts-liberation fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY env/requirements.txt env/requirements.txt
RUN pip install --no-cache-dir -r env/requirements.txt \
      requests pandas matplotlib pyyaml rapidfuzz
COPY . .
RUN if [ -f runner/requirements.txt ]; then pip install --no-cache-dir -r runner/requirements.txt; fi

# Default: build the pilot dataset and self-check it. Override CMD to run the runner, e.g.
#   docker run --rm -e OPENROUTER_API_KEY -v $PWD/data:/work/data -v $PWD/results:/work/results IMAGE \
#     python runner/run.py --models models/models.yaml --data data/ --out results/
CMD ["bash", "-lc", "python env/generate.py --n-pages 10 --seed 7 --out data/ && python env/capture.py --data data/ && python env/check.py --data data/"]
