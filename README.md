# Industrial OCR Engine (LLM-Based)

This project provides a robust OCR engine tailored for industrial document processing (acts, UPDs, contracts) using generative AI models (GigaChat) and traditional OCR as fallback.

## Setup

1.  **Prerequisites**:
    -   Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for Windows.
    -   Ensure `docker` and `docker-compose` commands work in your terminal.

2.  **Clone the repository** and navigate to `ocr-engine`.
2.  **Environment Variables**:
    Copy `.env.example` to `.env` and set your variables (especially `GIGACHAT_CREDENTIALS`).
    ```bash
    cp .env.example .env
    ```
3.  **Run with Docker Compose** (Recommended):
    ```bash
    docker-compose up --build
    ```
    This will start the API at `http://localhost:8000` and a PostgreSQL database.

## API Documentation

-   **Swagger UI**: `http://localhost:8000/docs`
-   **ReDoc**: `http://localhost:8000/redoc`

## Usage Workflow

1.  **Register a Model**: Use `POST /api/v1/models/` to add an LLM provider (e.g., GigaChat).
2.  **Create a Contract**: Use `POST /api/v1/contracts/` to define a JSON schema for a document type (e.g., "UPD").
3.  **Upload Document**: `POST /api/v1/documents/upload` with a PDF/Image. 
    The system will classify it and extract data based on the matching contract.
4.  **Retrieve Results**: `GET /api/v1/documents/{id}` to see extraction results.

## Development

-   **Run locally**:
    ```bash
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    ```
