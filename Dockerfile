FROM python:3.13.7-alpine3.22
ADD requirements.txt /opt/powermeter/
ADD main.py /opt/powermeter/
RUN pip install --root-user-action=ignore --use-pep517 -r /opt/powermeter/requirements.txt
CMD [ "/usr/bin/env", "python", "/opt/powermeter/main.py" ]
