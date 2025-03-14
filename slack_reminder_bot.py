import os
import time
import logging
import json
import threading
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request
from slackeventsapi import SlackEventAdapter

# Load environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Set your Slack channel ID

# Initialize Slack client
client = WebClient(token=SLACK_BOT_TOKEN)

# Create Flask app
app = Flask(__name__)

# Slack event adapter
slack_events_adapter = SlackEventAdapter(SLACK_SIGNING_SECRET, "/slack/events", app)

# Track user reactions
reaction_users = set()

# Send message with reactions
def send_reminder():
    try:
        response = client.chat_postMessage(
            channel=CHANNEL_ID,
            text="Reminder: Please confirm by reacting with ✅ or ❌."
        )
        message_ts = response["ts"]  # Get timestamp of the message
        return message_ts
    except SlackApiError as e:
        logging.error(f"Error sending message: {e.response['error']}")
        return None

# Track reactions
@slack_events_adapter.on("reaction_added")
def reaction_added(event_data):
    event = event_data["event"]
    user_id = event.get("user")
    reaction = event.get("reaction")

    if reaction in ["✅", "❌"]:
        reaction_users.add(user_id)  # Mark user as responded
        logging.info(f"User {user_id} reacted with {reaction}")

# Fetch users who haven't reacted
def get_users_without_reaction():
    try:
        response = client.conversations_members(channel=CHANNEL_ID)
        all_users = response["members"]
        non_responders = [user for user in all_users if user not in reaction_users]
        return non_responders
    except SlackApiError as e:
        logging.error(f"Error fetching users: {e.response['error']}")
        return []

# Send DM reminders to non-responders
def send_dm_reminders():
    non_responders = get_users_without_reaction()
    
    for user_id in non_responders:
        try:
            client.chat_postMessage(
                channel=user_id,
                text="Reminder: Please react to the message in the channel."
            )
            time.sleep(2)  # Prevent rate limits
        except SlackApiError as e:
            logging.error(f"Error sending DM to {user_id}: {e.response['error']}")

# Background task for reminders
def reminder_loop():
    while True:
        message_ts = send_reminder()
        if message_ts:
            time.sleep(10)  # Wait before sending DMs (adjust as needed)
            send_dm_reminders()
        time.sleep(10)  # Loop every 10 seconds (adjust as needed)

# Start the reminder loop in a separate thread
threading.Thread(target=reminder_loop, daemon=True).start()

# Start Flask app
if __name__ == "__main__":
    app.run(port=3000)
