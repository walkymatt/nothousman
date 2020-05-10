release: python manage.py migrate
web: uvicorn --host 0.0.0.0 --port $PORT games.asgi:application
