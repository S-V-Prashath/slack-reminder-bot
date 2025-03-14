import os
import json
import time
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

# Dictionary to track responses
reminder_responses = {}

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
    channel_id = payload["channel"]["id"]

    # Store response
    reminder_responses[user_id] = action

    # Acknowledge response
    slack_app.client.chat_postMessage(
        channel=user_id,
        text=f"✅ You selected: *{action}*"
    )

    return Response(status=200)

# Function to send reminders
def send_reminder(channel_id):
    global reminder_responses

    # Fetch users in the channel
    response = slack_app.client.conversations_members(channel=channel_id)
    all_users = set(response["members"])

    # Remove bot user
    bot_user_id = slack_app.client.auth_test()["user_id"]
    all_users.discard(bot_user_id)

    # Reset responses
    reminder_responses = {user: None for user in all_users}

    # Send message with buttons
    slack_app.client.chat_postMessage(
        channel=channel_id,
        text="🔔 *Reminder:* Please confirm your status:",
        attachments=[
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
        ]
    )

    # Wait for responses (Adjust as needed)
    time.sleep(60)  # Wait 60 seconds

    # Send reminders to those who didn't respond
    unresponsive_users = [user for user, response in reminder_responses.items() if response is None]

    if unresponsive_users:
        slack_app.client.chat_postMessage(
            channel=channel_id,
            text=f"⚠️ *Reminder:* The following users haven't responded yet:\n" +
                 "\n".join(f"<@{user}>" for user in unresponsive_users)
        )

        # Send private reminders
        for user in unresponsive_users:
            slack_app.client.chat_postMessage(
                channel=user,
                text="⏳ You haven't responded yet. Please select an option in the channel message."
            )

# Route to manually trigger reminder
@app.route("/send_reminder", methods=["POST"])
def trigger_reminder():
    data = request.json
    channel_id = data.get("channel_id")
    
    if not channel_id:
        return {"error": "Missing channel_id"}, 400
    
    send_reminder(channel_id)
    return {"message": "Reminder sent successfully"}, 200

# Start Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))  # Use Railway-assigned port
    app.run(host="0.0.0.0", port=port)
