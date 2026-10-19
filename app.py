
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode
from flask import redirect

import boto3
from authlib.integrations.flask_client import OAuth
from botocore.exceptions import BotoCoreError, ClientError
from flask import (
    Flask, flash, redirect, render_template, request,
    session, url_for
)
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv()

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "notes")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-2")
COGNITO_DOMAIN = os.environ["COGNITO_DOMAIN"].rstrip("/")
COGNITO_CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
COGNITO_USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
COGNITO_CLIENT_SECRET = os.environ["COGNITO_CLIENT_SECRET"]
REDIRECT_URI = os.environ.get(
    "COGNITO_REDIRECT_URI",
    "http://127.0.0.1:5000/callback"
)

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # Local HTTP development only
)

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)

oauth = OAuth(app)
oauth.register(
    name="cognito",
    client_id=COGNITO_CLIENT_ID,
    client_secret=COGNITO_CLIENT_SECRET,
    server_metadata_url=(
        f"https://cognito-idp.{AWS_REGION}.amazonaws.com/"
        f"{COGNITO_USER_POOL_ID}/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)

def current_user():
    return session.get("user")


def require_user():
    if not current_user():
        return redirect(url_for("login"))
    return None


@app.route("/")
def index():
    if not current_user():
        return redirect(url_for("login"))

    try:
        # Existing table uses id as its partition key.
        # Filter results to the authenticated Cognito user.
        response = table.scan()
        notes = [
            note for note in response.get("Items", [])
            if note.get("user_id") == current_user()["sub"]
        ]

        while "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            notes.extend(
                note for note in response.get("Items", [])
                if note.get("user_id") == current_user()["sub"]
            )

        notes.sort(
            key=lambda note: note.get("created_at", ""),
            reverse=True,
        )
    except (BotoCoreError, ClientError):
        app.logger.exception("DynamoDB read failed")
        flash("Could not load notes. Check AWS permissions.", "error")
        notes = []

    return render_template(
        "index.html",
        notes=notes,
        table=TABLE_NAME,
        user=current_user(),
    )


@app.route("/login")
def login():
    return oauth.cognito.authorize_redirect(REDIRECT_URI)


@app.route("/callback")
def callback():
    token = oauth.cognito.authorize_access_token()
    response = oauth.cognito.get(
        "https://ap-southeast-2bqvs5hrii.auth.ap-southeast-2.amazoncognito.com/oauth2/userInfo",
        token=token
    )
    profile = response.json()

    if not profile.get("sub"):
        return "Could not verify your Cognito identity.", 401

    session.clear()
    session["user"] = {
        "sub": profile["sub"],
        "email": profile.get("email", ""),
    }
    return redirect(url_for("index"))



from urllib.parse import urlencode
from flask import redirect, session

@app.route("/logout")
def logout():
    session.clear()

    params = {
        "client_id": COGNITO_CLIENT_ID,
        "logout_uri": "http://127.0.0.1:5000/",
    }

    logout_url = f"{COGNITO_DOMAIN}/logout?{urlencode(params)}"
    return redirect(logout_url)

@app.route("/add", methods=["POST"])
def add():
    denied = require_user()
    if denied:
        return denied

    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()

    if not title:
        flash("Title is required.", "error")
        return redirect(url_for("index"))

    try:
        table.put_item(Item={
            "id": str(uuid.uuid4()),
            "user_id": current_user()["sub"],
            "title": title,
            "body": body,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        flash("Note added.", "ok")
    except (BotoCoreError, ClientError):
        app.logger.exception("DynamoDB write failed")
        flash("Could not save note. Check AWS permissions.", "error")

    return redirect(url_for("index"))


@app.route("/edit/<note_id>", methods=["POST"])
def edit(note_id):
    denied = require_user()
    if denied:
        return denied

    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()

    if not title:
        flash("Title is required.", "error")
        return redirect(url_for("index"))

    try:
        table.update_item(
            Key={"id": note_id},
            UpdateExpression="SET title = :t, body = :b",
            ExpressionAttributeValues={
                ":t": title,
                ":b": body,
                ":owner": current_user()["sub"],
            },
            ConditionExpression="user_id = :owner",
        )
        flash("Note updated.", "ok")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            flash("Note not found or you don't own it.", "error")
        else:
            app.logger.exception("DynamoDB update failed")
            flash("Could not update note.", "error")
    except BotoCoreError:
        app.logger.exception("DynamoDB update failed")
        flash("Could not update note.", "error")

    return redirect(url_for("index"))


@app.route("/delete/<note_id>", methods=["POST"])
def delete(note_id):
    denied = require_user()
    if denied:
        return denied

    try:
        table.delete_item(
            Key={"id": note_id},
            ConditionExpression="user_id = :owner",
            ExpressionAttributeValues={
                ":owner": current_user()["sub"]
            },
        )
        flash("Note deleted.", "ok")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            flash("Note not found or you don't own it.", "error")
        else:
            app.logger.exception("DynamoDB delete failed")
            flash("Could not delete note.", "error")
    except BotoCoreError:
        app.logger.exception("DynamoDB delete failed")
        flash("Could not delete note.", "error")

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1",
        host="127.0.0.1",
        port=5000,
    )
