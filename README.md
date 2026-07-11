# Webbly - A Distributed Web Scraping App

Webbly is a distributed Web Scraping App that collects product information from multiple pages of a website.

The application begins with one page, identifies other related pages, and continues crawling them automatically. Instead of processing every page one after another, the work can be shared between multiple workers. This allows several pages to be processed at the same time and makes the crawler easier to scale.

The extracted information is stored during the crawl and can later be exported to a JSON file.

## How it works

The application follows a simple process:

1. The user starts the crawler.
2. The crawler begins with a configured starting page.
3. Product information is collected from that page.
4. Links to additional product pages/any type of pages are discovered.
5. Those pages are added to a shared work queue.
6. Available workers process the pages.
7. The crawl finishes when there are no pages left to process.
8. The collected products can be exported to a JSON file.

## Why multiple workers are used

Web pages can be shared between multiple workers.

## Architecture

```text
main.py
   │
   │ sends the first crawl task
   ▼
Redis
   │
   ├── worker1
   └── worker2
          │
          ├── download pages
          ├── extract products
          ├── discover pagination links
          └── submit new crawl tasks
```

## Setup

Clone the repository and enter the project directory:

```bash
git clone <repository-url>
cd webscrape-distributed-app
```

Create a Python virtual environment:

```bash
python3 -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Install the Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Start Redis

Redis runs inside Docker.

Start it from the project directory:

```bash
docker compose up -d redis
```

Check its status:

```bash
docker compose ps
```

Test the Redis connection:

```bash
docker compose exec redis redis-cli ping
```

Expected output:

```text
PONG
```

## Start Celery workers

Open a new terminal for the first worker:

```bash
cd webscrape-distributed-app
source .venv/bin/activate

celery -A tasks:app worker \
  --loglevel=INFO \
  --pool=prefork \
  --concurrency=2 \
  --hostname=worker1@%h
```

Open another terminal for the second worker:

```bash
cd webscrape-distributed-app
source .venv/bin/activate

celery -A tasks:app worker \
  --loglevel=INFO \
  --pool=prefork \
  --concurrency=2 \
  --hostname=worker2@%h
```

Wait until both terminals display:

```text
ready
```

You can verify that both workers are online:

```bash
celery -A tasks:app status
```

Expected output:

```text
worker1@...: OK
worker2@...: OK

2 nodes online.
```

## Run the crawler

Open another terminal:

```bash
cd webscrape-distributed-app
source .venv/bin/activate
python main.py
```
