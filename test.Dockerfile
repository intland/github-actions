FROM intland/github-runner
ADD libs/ /app/libs/
ADD test/main.py /app/

CMD ["/app/main.py"]
