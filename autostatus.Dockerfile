FROM intland/github-runner
ADD libs/ /app/libs/
ADD autostatus/main.py /app/

CMD ["/app/main.py"]
