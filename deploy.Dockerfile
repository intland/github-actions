FROM intland/github-runner
ADD libs/ /app/libs/
ADD deploy/main.py /app/

CMD ["/app/main.py"]
