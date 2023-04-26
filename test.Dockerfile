FROM intland/github-runner
ADD libs/ /app/libs/
ADD test/main.py /app/
ADD test/job_config.json /app/

CMD ["/app/main.py"]
