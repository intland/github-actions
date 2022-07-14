FROM intland/github-runner
ADD libs/ /app/libs/
ADD merge_branch/main.py /app/

CMD ["/app/main.py"]
