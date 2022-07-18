FROM intland/github-runner:py3.9
ADD libs/ /app/libs/
ADD merge_branch/main.py /app/

CMD ["/app/main.py"]
