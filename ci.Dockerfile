FROM intland/github-runner
ADD libs/ /app/libs/
ADD ci/main.py /app/

CMD ["/app/main.py"]
