# OCR Engine

Industrial-grade OCR backend service with GigaChat integration.

## Features

-   **Sync & Async Processing**: `POST /process` and `POST /process_async`.
-   **Dynamic Schemas**: Document types and extraction schemas are stored in PostgreSQL.
-   **LLM Powered**: Uses GigaChat (Multimodal) for classification and extraction.
-   **Scalable Architecture**: Dockerized, stateless API, background task processing (expandable to Celery).

## Setup

1.  **Environment Variables**:
    Copy `.env.example` to `.env` and fill in your credentials.
    ```bash
    cp .env.example .env
    ```

2.  **Docker Start**:
    ```bash
    docker-compose up --build
    ```

3.  **Local Dev**:
    ```bash
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    ```

## API Usage

### Sync process
```bash
curl -X POST "http://localhost:8000/process" -F "file=@/path/to/doc.pdf"
```

### Async process
```bash
curl -X POST "http://localhost:8000/process_async" -F "file=@/path/to/doc.pdf"
# Returns { "job_id": "uuid..." }
```

### Check Result
```bash
curl "http://localhost:8000/result/{job_id}"
```
