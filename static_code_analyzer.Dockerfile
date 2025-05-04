FROM intland/github-runner
ADD libs/ /app/libs/
ADD static_code_analyzer/main.py /app/

CMD ["/app/main.py"]
