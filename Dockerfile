FROM python:3.13.5-alpine3.22

WORKDIR /app

COPY ./requirements.txt /app/
RUN pip install -r requirements.txt

COPY ./app.py /app/

RUN apk add --no-cache strace

CMD ["flask", "run", "--host", "0.0.0.0"]