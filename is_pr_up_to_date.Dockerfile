FROM intland/github-runner:py3.9
ADD libs/ /app/libs/
ADD is_pr_up_to_date/main.py /app/

CMD ["/app/main.py"]

