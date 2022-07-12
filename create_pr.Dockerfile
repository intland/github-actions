FROM intland/github-runner
ADD libs/ /app/libs/
ADD create_pr/main.py /app/

CMD ["/app/main.py"]
