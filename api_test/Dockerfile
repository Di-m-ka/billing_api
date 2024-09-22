FROM python:3.9
WORKDIR /app
COPY ./main.py /app/
COPY ./requirements.txt /app/
RUN pip install --no-cache-dir --upgrade -r requirements.txt && pip install --no-cache-dir --upgrade  fastapi[standard]
CMD ["fastapi", "run", "main.py", "--port", "80"]