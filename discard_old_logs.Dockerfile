FROM intland/github-runner
ADD libs/ /app/libs/
ADD discard_old_logs/main.py /app/

CMD ["/app/main.py"]
