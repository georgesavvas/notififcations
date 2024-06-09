FROM python:2.7
ARG UID
ARG GID

ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y lsb-release sudo && apt-get clean all && \
    adduser --uid $UID --gid $GID --disabled-password --gecos "" george && \
    usermod -d /users/george george && \
    echo 'george ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

RUN apt install python3.7 python3-pip python3-venv -y
RUN python3 -m pip install --upgrade pip

WORKDIR /opt/cue_rest_api
RUN chmod 777 /opt/cue_rest_api
USER george

COPY requirements.txt .

ENV VIRTUAL_ENV=/opt/cue_rest_api/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --upgrade pip
RUN pip install --upgrade -r requirements.txt

COPY source/ .

CMD ["./bin/rez_cue_rest_api"]
