FROM intland/github-runner:py3.9
ADD libs/ /app/libs/
ADD enforce_tracker_id/main.py /app/

CMD ["/app/main.py"]

