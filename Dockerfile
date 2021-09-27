FROM python:3.6-slim
COPY requirements.txt /
RUN pip3 install -r /requirements.txt
COPY openssl.cnf /etc/ssl/openssl.cnf
COPY . /app
WORKDIR /app
CMD ["python", "evobeat.py", "run", "--name", "test_collector"]
