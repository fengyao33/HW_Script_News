pip freeze > requirement.txt 

pip install -r requirements.txt

gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

python wsgi.py