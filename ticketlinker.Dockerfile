FROM intland/github-runner
ADD libs/ /app/libs/
ADD ticketlinker/main.py /app/

CMD ["/app/main.py"]
