FROM intland/github-runner
ADD libs/ /app/libs/
ADD sonar/main.py /app/

CMD ["/app/main.py"]
