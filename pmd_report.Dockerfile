FROM intland/github-runner
ADD libs/ /app/libs/
ADD pmd_report/main.py /app/

CMD ["/app/main.py"]
