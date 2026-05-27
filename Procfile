release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: python manage.py migrate --noinput && gunicorn consulte.wsgi --log-file -
