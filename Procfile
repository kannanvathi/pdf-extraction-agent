web: gunicorn --chdir /var/app/current --pythonpath /var/app/current --bind 0.0.0.0:${PORT:-8000} --worker-class uvicorn.workers.UvicornWorker application:application
