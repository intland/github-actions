FROM intland/github-runner
ADD libs/ /app/libs/
ADD test2/main.py /app/

CMD ["/app/main.py"]
