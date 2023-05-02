FROM intland/github-runner
ADD libs/ /app/libs/
ADD get_extra_parameters/main.py /app/
ADD get_extra_parameters/*.json /app/

CMD ["/app/main.py"]
