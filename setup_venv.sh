python3 -m venv ./venv
source ./venv/bin/activate

(cd acapy-plugins && poetry install --extras aca-py)

pip install textual
