# Руководство по развертыванию: Industrial OCR Engine (Linux Server)

Это руководство описывает процесс развертывания OCR-движка на корпоративном Linux-сервере с использованием Docker.

## 1. Требования (Prerequisites)
-   **Linux Server** (Ubuntu, Debian, CentOS и др.)
-   **Docker** (версия 20+)
-   **Docker Compose** (версия 2.0+)
-   **Доступ в Интернет** (для первичного скачивания образов Python, Postgres, Tesseract).
    -   *Если сервер изолирован (без интернета)*, вам потребуется сохранить образы локально (`docker save`) и перенести их вручную.

## 2. Пошаговая установка

### Шаг 1: Перенос файлов
Скопируйте всю папку проекта `ocr-engine` на ваш сервер (например, в `/opt/ocr-engine`).
Необходимые файлы:
-   Папка `app/`
-   Файл `docker-compose.yml`
-   Файл `Dockerfile`
-   Файл `requirements.txt`
-   Файл `.env.example`

### Шаг 2: Настройка конфигурации
1.  Перейдите в папку проекта:
    ```bash
    cd /opt/ocr-engine
    ```
2.  Создайте файл `.env` из примера:
    ```bash
    cp .env.example .env
    ```
3.  **Отредактируйте `.env` (ОБЯЗАТЕЛЬНО)**:
    ```bash
    nano .env
    ```
    -   Впишите `GIGACHAT_CREDENTIALS` (Ваш ключ авторизации GigaChat).
    -   Задайте `POSTGRES_PASSWORD` (Придумайте надежный пароль для базы данных).
    -   (Опционально) Измените пользователя `POSTGRES_USER` и имя базы `POSTGRES_DB`.

### Шаг 3: Запуск (Launch)
Выполните команду (обратите внимание на пробел вместо дефиса, это современная V2 версия):

```bash
docker compose up -d --build
```
*Если команда `docker compose` не найдена, используйте `docker-compose` (старая версия), но она может конфликтовать с python-пакетами.*

-   **--build**: Гарантирует пересборку образа из Dockerfile.
-   **-d**: Detached mode (запуск в фоне, чтобы терминал не блокировался).

### Шаг 4: Проверка (Verification)
Проверьте, что контейнеры запущены:
```bash
docker compose ps
```
Вы должны увидеть сервисы `web` и `db` со статусом `Up`.

Проверьте логи на наличие ошибок:
```bash
docker compose logs -f web
```
Дождитесь сообщения: `Application startup complete`. Нажмите `Ctrl+C`, чтобы выйти из логов.

## 3. Использование API

API будет доступен по адресу вашего сервера на порту 8000:
**`http://<IP_АДРЕС_СЕРВЕРА>:8000`**

-   **Интерактивная документация (Swagger UI)**: `http://<IP_АДРЕС_СЕРВЕРА>:8000/docs`
    *(Здесь можно тестировать запросы прямо из браузера)*
-   **ReDoc**: `http://<IP_АДРЕС_СЕРВЕРА>:8000/redoc`

## 4. Решение проблем (Troubleshooting)

**Ошибка "Connection Refused"**:
-   Проверьте, открыт ли порт 8000 в фаерволе сервера.
    ```bash
    sudo ufw allow 8000
    ```

**Ошибка "Permission Denied" (Docker)**:
-   Если Docker требует права root, добавляйте `sudo` перед командами или добавьте пользователя в группу docker:
    ```bash
    sudo usermod -aG docker $USER
    ```
    (Потребуется перелогиниться).

**Ошибка "DNS / Network Errors" при сборке**:
-   Если сервер находится за корпоративным прокси или имеет ограничения сети, Docker может не видеть интернет.
-   Попробуйте добавить DNS Google в настройки Docker (`/etc/docker/daemon.json`):
    ```json
    { "dns": ["8.8.8.8", "1.1.1.1"] }
    ```
    Затем перезапустите Docker: `sudo systemctl restart docker`.
**Ошибка "unknown shorthand flag" или "docker: 'compose' is not a docker command"**:
Это значит, что у вас не установлен плагин Docker Compose V2.
**Решение (установка V2 глобально для всех пользователей):**
1.  Создайте папку для плагинов (понадобится пароль sudo):
    ```bash
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    ```
2.  Скачайте плагин туда:
    ```bash
    sudo curl -SL https://github.com/docker/compose/releases/download/v2.24.6/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
    ```
3.  Дайте права на выполнение:
    ```bash
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ```
4.  Проверьте версию:
    ```bash
    docker compose version
    ```
5.  Запускайте снова: `sudo docker compose up -d --build`
