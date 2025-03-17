import os
import json
import time
import schedule
import threading
from flask import Flask, request, Response
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Slack credentials
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("Missing Slack credentials. Check environment variables.")

# Initialize Slack app
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
handler = SlackRequestHandler(slack_app)

# Store user-specific settings
user_settings = {}

# Default settings (for new users)
default_settings = {
    "punch_in_time": "10:00",
    "punch_out_time": "19:00",
    "reminder_interval": 15,  # in minutes
    "punch_in_message": "⏳ It's time to punch in.",
    "punch_out_message": "⏳ Time to punch out.",
    "reminder_punch_in": "🔔 Still not punched in? Please do it.",
    "reminder_punch_out": "🔔 Still not punched out? Please do it."
}

# Route for Slack Events
@app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

# Route for Slack Interactions (buttons)
@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    payload = json.loads(request.form["payload"])
    user_id = payload["user"]["id"]
    action = payload["actions"][0]["value"]

    # Mark user as responded
    user_settings[user_id]["responded"] = True

    # Acknowledge response
    slack_app.client.chat_postMessage(
        channel=user_id,
        text=f"✅ You selected: *{action}*"
    )

    return Response(status=200)

# Function to send reminders
def send_reminder(user_id):
    user_data = user_settings.get(user_id, default_settings)
    
    # Send Punch-In or Punch-Out reminder
    message_text = user_data["punch_in_message"] if user_data["reminder_type"] == "punch_in" else user_data["punch_out_message"]

    slack_app.client.chat_postMessage(channel=user_id, text=message_text, attachments=[
        {
            "text": "Select an option:",
            "fallback": "You are unable to choose an option",
            "callback_id": "reminder_buttons",
            "color": "#3AA3E3",
            "actions": [
                {
                    "name": "response",
                    "text": "✅ Yes",
                    "type": "button",
                    "value": "Yes"
                },
                {
                    "name": "response",
                    "text": "❌ No",
                    "type": "button",
                    "value": "No"
                }
            ]
        }
    ])

    # Start checking for unresponsive users
    user_settings[user_id]["responded"] = False
    check_reminders(user_id)

# Function to check for unresponsive users
def check_reminders(user_id):
    user_data = user_settings.get(user_id, default_settings)
    
    while not user_data.get("responded"):
        time.sleep(user_data["reminder_interval"] * 60)

        if user_data.get("responded"):
            break

        reminder_message = user_data["reminder_punch_in"] if user_data["reminder_type"] == "punch_in" else user_data["reminder_punch_out"]
        slack_app.client.chat_postMessage(channel=user_id, text=reminder_message)

# Commands for users to customize their settings
@slack_app.command("/set_punch_in")
def set_punch_in(ack, respond, command):
    ack()
    user_id = command["user_id"]
    user_settings.setdefault(user_id, default_settings.copy())["punch_in_time"] = command["text"]
    respond(f"✅ Your Punch-In time has been set to *{command['text']}*.")

@slack_app.command("/set_punch_out")
def set_punch_out(ack, respond, command):
    ack()
    user_id = command["user_id"]
    user_settings.setdefault(user_id, default_settings.copy())["punch_out_time"] = command["text"]
    respond(f"✅ Your Punch-Out time has been set to *{command['text']}*.")

@slack_app.command("/set_reminder_interval")
def set_reminder_interval(ack, respond, command):
    ack()
    user_id = command["user_id"]
    try:
        interval = int(command["text"])
        user_settings.setdefault(user_id, default_settings.copy())["reminder_interval"] = interval
        respond(f"✅ Your reminder interval has been set to *{interval} minutes*.")
    except ValueError:
        respond("⚠️ Please enter a valid number.")

@slack_app.command("/set_messages")
def set_messages(ack, respond, command):
    ack()
    user_id = command["user_id"]
    params = command["text"].split("|")
    if len(params) != 4:
        respond("⚠️ Use: `punch-in-msg | punch-out-msg | remind-in-msg | remind-out-msg`")
        return
    user_settings.setdefault(user_id, default_settings.copy()).update({
        "punch_in_message": params[0].strip(),
        "punch_out_message": params[1].strip(),
        "reminder_punch_in": params[2].strip(),
        "reminder_punch_out": params[3].strip()
    })
    respond("✅ Messages updated successfully!")

@slack_app.command("/view_settings")
def view_settings(ack, respond, command):
    ack()
    respond(str(user_settings.get(command["user_id"], default_settings)))

@slack_app.command("/help")
def help_command(ack, respond):
    ack()
    respond("Here are the available commands:\n" + "\n".join(user_settings.keys()))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
