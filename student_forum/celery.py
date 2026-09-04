import os
from celery import Celery
from kombu import Queue
import ssl

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'student_forum.settings')

app = Celery('student_forum')

# Using a string here means the worker doesn't have to serialize the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Define multiple queues with priorities and dedicated workers
# grades: Dedicated worker for all grade checking operations (WebDriver intensive)
# general: Worker for general tasks like emails, notifications, etc.
# high: Interactive user tasks with high priority
# default: Regular tasks (fallback queue)
# low: Background batch jobs
app.conf.task_queues = (
    Queue('grades', routing_key='grades.#'),    # Grade checking tasks (dedicated worker)
    Queue('general', routing_key='general.#'),  # General tasks (emails, notifications, etc.)
    Queue('high', routing_key='high.#'),        # Interactive user tasks
    Queue('default', routing_key='default.#'),  # Regular tasks (fallback)
    Queue('low', routing_key='low.#'),          # Background batch jobs
)

# Set default routing configuration
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange_type = 'direct'
app.conf.task_default_routing_key = 'default.default'

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Memory optimization settings for Heroku
app.conf.worker_prefetch_multiplier = 1  # Reduce task prefetching
app.conf.worker_max_tasks_per_child = 10  # Restart worker after 10 tasks to free memory
app.conf.worker_disable_rate_limits = True
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    'cleanup-expired-community-lunches': {
        'task': 'forum.tasks.cleanup_expired_community_lunches_task',
        'schedule': 60.0 * 60,
        'options': {'queue': 'low', 'routing_key': 'low.community_cleanup'},
    },
    'check-all-user-grades': {
        'task': 'forum.tasks.periodic_grade_check_trigger',
        'schedule': 60.0 * 60,  # Every 60 minutes
        'options': {'queue': 'grades', 'routing_key': 'grades.trigger'}
    },
    # Alternative: Use batched approach (comment out above and uncomment below)
    # 'check-all-user-grades-batched': {
    #     'task': 'forum.tasks.check_user_grades_batched_dispatch',
    #     'schedule': 30.0 * 60,  # Every 30 minutes
    #     'options': {'queue': 'grades', 'routing_key': 'grades.coordination'},
    #     'kwargs': {'batch_size': 1}  # Process 1 user at a time for memory efficiency
    # },
}

# Reduced time limits for memory efficiency
CELERY_TASK_SOFT_TIME_LIMIT = 45 
CELERY_TASK_TIME_LIMIT = 90 

app.conf.timezone = 'UTC'

# Ensure compatibility with Celery 6.0 and above
app.conf.broker_connection_retry_on_startup = True

# Respect Redis/Celery transport options set in Django settings.
from django.conf import settings as django_settings

# Apply transport options if provided in settings (e.g. max_connections)
try:
    transport_opts = getattr(django_settings, 'CELERY_BROKER_TRANSPORT_OPTIONS', None)
    if transport_opts:
        app.conf.broker_transport_options = transport_opts
except Exception:
    # Fail quietly - defaults will be used
    pass

# Configure SSL for Redis broker if the REDIS_URL uses rediss://
# Clean URL parameters and apply proper SSL configuration
try:
    broker_url = getattr(django_settings, 'CELERY_BROKER_URL', os.getenv('REDIS_URL', ''))
    if broker_url and broker_url.startswith('rediss://'):
        # Remove ssl_cert_reqs parameter from URL if present (it conflicts with our SSL config)
        import urllib.parse
        parsed_url = urllib.parse.urlparse(broker_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Remove ssl_cert_reqs from query parameters
        if 'ssl_cert_reqs' in query_params:
            del query_params['ssl_cert_reqs']
            print(f"Removed ssl_cert_reqs parameter from Redis URL")
            
        # Reconstruct URL without ssl_cert_reqs parameter
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        cleaned_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
        
        # Update broker URL
        app.conf.broker_url = cleaned_url
        
        # Get SSL configuration from Django settings
        ssl_opts = getattr(django_settings, 'CELERY_BROKER_USE_SSL', None)
        
        if ssl_opts is not None:
            # Use the SSL configuration from Django settings
            app.conf.broker_use_ssl = ssl_opts
            print(f"Using SSL config from Django settings")
        else:
            # Default configuration for Heroku Redis (self-signed certificates)
            app.conf.broker_use_ssl = {
                'ssl_cert_reqs': ssl.CERT_NONE,      # Don't verify certificate
                'ssl_check_hostname': False,         # Don't verify hostname
                'ssl_ca_certs': None,                # No CA certificates
            }
            print(f"Using default Heroku SSL config (CERT_NONE)")
            
        # Also configure result backend SSL if using Redis for results
        result_backend = getattr(django_settings, 'CELERY_RESULT_BACKEND', '')
        if result_backend and result_backend.startswith('rediss://'):
            # Clean result backend URL too
            app.conf.result_backend = cleaned_url
            
            redis_backend_ssl = getattr(django_settings, 'CELERY_REDIS_BACKEND_USE_SSL', None)
            if redis_backend_ssl is not None:
                app.conf.redis_backend_use_ssl = redis_backend_ssl
            else:
                app.conf.redis_backend_use_ssl = {
                    'ssl_cert_reqs': ssl.CERT_NONE,
                    'ssl_check_hostname': False,
                    'ssl_ca_certs': None,
                }
                
except Exception as e:
    print(f"Error configuring Celery SSL: {e}")
    pass
