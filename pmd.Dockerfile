FROM intland/github-runner
ADD libs/ /app/libs/
ADD pmd/main.py /app/

CMD ["/app/main.py"]
