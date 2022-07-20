FROM intland/github-runner:py3.9
ADD libs/ /app/libs/
ADD create_pr/main.py /app/

CMD ["/app/main.py"]
