FROM intland/github-runner
ADD libs/ /app/libs/
ADD autopr/main.py /app/

CMD ["/app/main.py"]
