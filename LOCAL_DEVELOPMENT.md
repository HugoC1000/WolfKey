# WolfKey Grade Checking System

## Overview

The grade checking system uses Celery with Redis and separates workload into two dedicated worker types:
- grades_worker: Dedicated to grade-checking tasks that use Selenium/WebDriver and are memory-intensive.
- general_worker: Handles all other tasks (emails, notifications, autocomplete, interactive tasks).


## Local Development

### 1. Setup Redis
```bash
brew install redis
brew services start redis
redis-cli ping  # Should return: PONG
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the System (4 terminals)

Run a dedicated grades worker (single concurrency, use --pool=solo for safer WebDriver usage):
```bash
celery -A student_forum worker --loglevel=info --concurrency=1 -Q grades --pool=solo
```

Run a general worker for the rest of the tasks:
```bash
general_worker: celery -A student_forum worker --loglevel=info --concurrency=1 -Q general,high,default,low --loglevel=debug --pool=solo

```

Run Celery Beat (scheduler):
```bash
celery -A student_forum beat --loglevel=info
```

Run the Django development server:
```bash
python manage.py runserver
```

### Schedule Import

The screenshot and pasted-text schedule importer requires a Gemini API key:

```bash
GEMINI_API_KEY=your-key
```

It uses `gemini-3.5-flash-lite` by default. Override the model only when needed:

```bash
SCHEDULE_IMPORT_GEMINI_MODEL=gemini-3.5-flash-lite
```

Gemini-backed previews are limited to 4 requests per authenticated user per
hour. Override the rate when needed:

```bash
SCHEDULE_IMPORT_RATE=4/hour
```

## Testing

### Manual Grade Checking
```bash
# Check all users' grades (dispatches grade tasks)
python manage.py check_grades

# Check a specific user's grades
python manage.py check_grades --user-email student@wpga.ca
```

### Monitor Tasks (Optional)
```bash
pip install flower
celery -A student_forum flower
# Visit http://localhost:5555
```

## How It Works

### System Architecture
1. Celery Beat schedules periodic triggers (for example, `periodic_grade_check_trigger`) which dispatch coordination tasks to the `grades` queue.
2. The `grades_worker` consumes from the `grades` queue and is responsible for all WebDriver-heavy grade checks (single-concurrency recommended).
3. The `general_worker` consumes from the `general`, `high`, `default`, and `low` queues and handles email notifications, autocomplete, and other lightweight background work.
4. Separating workers prevents WebDriver tasks from starving other tasks for memory or CPU.

### Task Types
- `check_all_user_grades` / `periodic_grade_check_trigger` - Coordinates and dispatches grade checks (sent to `grades` queue).
- `check_single_user_grades` - Performs a grade check for one user (runs on `grades` queue).
- `send_email_notification` - Sent to the `general` queue.
- `autocomplete_courses` / `auto_complete_courses` - Sent to the `general` queue.

## Heroku Deployment

### Required Add-ons
```bash
# Add Redis addon
heroku addons:create heroku-redis:mini

# Check Redis URL
heroku config:get REDIS_URL
```

### Procfile Processes (recommended)
```
web: gunicorn student_forum.wsgi --log-file -
grades_worker: celery -A student_forum worker --loglevel=info --concurrency=1 -Q grades --pool=solo
general_worker: celery -A student_forum worker --loglevel=info --concurrency=2 -Q general,high,default,low
beat: celery -A student_forum beat --loglevel=info
```

### Scaling
```bash
# Scale the general worker independently
heroku ps:scale general_worker=1 beat=1 web=1

# If grade checks are heavy, add more grades workers carefully (use small dynos or single concurrency)
heroku ps:scale grades_worker=1
```

### Heroku Logs
```bash
# View logs for the general worker
heroku logs -t --dyno general_worker

# View logs for the grades worker
heroku logs -t --dyno grades_worker

# View beat logs
heroku logs -t --dyno beat
```
