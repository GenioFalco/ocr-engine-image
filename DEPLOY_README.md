# Deployment Guide: Industrial OCR Engine (Linux Server)

This guide describes how to deploy the OCR Engine on a company Linux server using Docker.

## 1. Prerequisites
-   **Linux Server** (Ubuntu, Debian, CentOS, etc.)
-   **Docker** installed (v20+)
-   **Docker Compose** installed (v2.0+)
-   **Internet Access** (initially) to download Docker images (Python, Postgres, Tesseract dependencies).
    -   *If the server is offline (air-gapped)*, you will need to save images locally (`docker save`) and transfer them.

## 2. Installation Steps

### Step 1: Transfer Files
Copy the entire project folder to your server (e.g., `/opt/ocr-engine`).
Files needed:
-   `app/` (folder)
-   `docker-compose.yml`
-   `Dockerfile`
-   `requirements.txt`
-   `.env.example`

### Step 2: Configuration
1.  Navigate to the folder:
    ```bash
    cd /opt/ocr-engine
    ```
2.  Create the `.env` file:
    ```bash
    cp .env.example .env
    ```
3.  **Edit `.env` (CRITICAL)**:
    ```bash
    nano .env
    ```
    -   Set `GIGACHAT_CREDENTIALS` (Your Auth Key).
    -   Set `POSTGRES_PASSWORD` (Change default password for security).
    -   Set `POSTGRES_USER` and `POSTGRES_DB` if desired.

### Step 3: Launch
Run the following command to build and start the containers in the background:

```bash
docker-compose up -d --build
```

-   **--build**: Ensures the image is built from the Dockerfile.
-   **-d**: Detached mode (runs in background).

### Step 4: Verification
Check if containers are running:
```bash
docker-compose ps
```
You should see `web` and `db` services with status `Up`.

Check logs to ensure no errors:
```bash
docker-compose logs -f web
```
Wait until you see: `Application startup complete`.

## 3. Accessing the API

The API will be available at:
**`http://<YOUR_SERVER_IP>:8000`**

-   **Interactive Docs (Swagger UI)**: `http://<YOUR_SERVER_IP>:8000/docs`
-   **ReDoc**: `http://<YOUR_SERVER_IP>:8000/redoc`

## 4. Troubleshooting

**"Connection Refused"**:
-   Check if firewall (ufw/iptables) allows port `8000`.
    ```bash
    sudo ufw allow 8000
    ```

**"Permission Denied" (Docker)**:
-   Run requests with `sudo` or add your user to the docker group: `sudo usermod -aG docker $USER`.

**"DNS / Network Errors during Build"**:
-   If the server has restricted internet, you might need to configure Docker daemon DNS:
    File: `/etc/docker/daemon.json`
    ```json
    { "dns": ["8.8.8.8", "1.1.1.1"] }
    ```
    Then restart docker: `sudo systemctl restart docker`.
