FROM intland/github-runner

RUN pip install -U api4jenkins

ADD libs/ /app/libs/
ADD discard_old_builds/main.py /app/

CMD ["/app/main.py"]
