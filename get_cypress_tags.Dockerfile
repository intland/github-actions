FROM intland/github-runner
ADD libs/ /app/libs/
ADD get_cypress_tags/main.py /app/

CMD ["/app/main.py"]
