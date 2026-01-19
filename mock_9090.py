import http.client
from flask import Flask

mock = Flask(__name__)
HEADERS = {"Content-Type": "text/plain", "Access-Control-Allow-Origin": "*"}

@mock.route("/calc/sqrt/<n>", methods=["GET"])
def sqrt(n):
    if str(n) == "64":
        return ("8", http.client.OK, HEADERS)
    return ("0", http.client.OK, HEADERS)

if __name__ == "__main__":
    mock.run(host="127.0.0.1", port=9090)
