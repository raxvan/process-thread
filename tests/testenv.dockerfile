
FROM python:3.8-slim

RUN pip3 install --upgrade pip && pip3 install \
	pudb

