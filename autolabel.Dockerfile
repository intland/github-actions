FROM intland/github-runner
ADD libs/ /app/libs/
ADD autolabel/main.py /app/

CMD ["/app/main.py"]
