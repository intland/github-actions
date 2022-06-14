FROM intland/github-runner
ADD libs/ /app/libs/
ADD autoassign/main.py /app/

CMD ["/app/main.py"]
