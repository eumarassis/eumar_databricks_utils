import os
import requests
from urllib.parse import urlencode, quote_plus
from flask import Flask, request, jsonify
from threading import Thread
import time
# Flask App for Handling Redirects
app = Flask(__name__)
CLIENT_ID = os.getenv("DATABRICKS_CLIENT_ID")

CLIENT_SECRET = os.getenv("DATABRICKS_CLIENT_SECRET")

REDIRECT_URI = os.getenv("DATABRICKS_REDIRECT_URI", "http://127.0.0.1:5098/callback")

WORKSPACE_URL = os.getenv('WORKSPACE_URL')
AUTH_URL = f"https://{WORKSPACE_URL}/oidc/v1/authorize"

TOKEN_URL = f"https://{WORKSPACE_URL}/oidc/v1/token"

WAREHOUSE_ID = os.getenv("WAREHOUSE_ID")


authorization_code = None  # Global variable to store the code


def get_authorization_url():

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "sql offline_access"
    }

    return f"{AUTH_URL}?{urlencode(params, quote_via=quote_plus)}"


def exchange_code_for_token(auth_code: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    response = requests.post(TOKEN_URL, data=data)
    response.raise_for_status()
    return response.json()


def query_databricks(access_token: str, query: str):

    statements_url =  f"https://{WORKSPACE_URL}/api/2.0/sql/statements"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {"statement": query, "warehouse_id": WAREHOUSE_ID, "parameters": 
               [
                    {
                    "name": "date",
                    "type": "DATE",
                    "value": "2016-02-01"
                    }
                ]}

    resp = requests.post(statements_url, headers=headers, json=payload)

    resp.raise_for_status()

    return resp.json()


@app.route("/callback", methods=["GET"])
def handle_callback():
    """Handle the OAuth2 redirect."""
    global authorization_code
    authorization_code = request.args.get("code")
    if authorization_code:
        return jsonify({"message": "Authorization code received", "code": authorization_code})
    return jsonify({"error": "No authorization code received"}), 400


if __name__ == "__main__":
    # Step 1: Start the Flask app for redirect handling
    from threading import Thread

    def run_flask_app():
        app.run(port=5098, debug=False)

    flask_thread = Thread(target=run_flask_app,daemon=True)
    flask_thread.start()

    # Step 2: Direct user to authorize
    print("Go to this URL to authorize your application:")
    print(get_authorization_url())

    # Step 3: Wait for the authorization code
    # Step 3: Wait for the authorization code
    print("Waiting for the authorization code...")
    while not authorization_code:
        time.sleep(1)  # Check every second

    print("Authorization code received. Querying Databricks.")
    
    # Step 4: Retrieve the access token
    token_data = exchange_code_for_token(authorization_code)
    access_token = token_data["access_token"]

    # Step 5: Query Databricks SQL
    sql_query = "SELECT count(1) as trip_count, pickup_zip FROM samples.nyctaxi.trips GROUP BY pickup_zip LIMIT 10"
    results = query_databricks(access_token, sql_query)
    print("Sample NYC Taxi Rides:", results)