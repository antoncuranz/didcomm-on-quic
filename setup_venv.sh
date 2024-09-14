python3 -m venv ./venv
source ./venv/bin/activate

(cd acapy-plugins/serviceregistry_protocol && poetry install --extras aca-py)
#(cd acapy-plugins/http3_transport && poetry install --extras aca-py)

pip install textual
