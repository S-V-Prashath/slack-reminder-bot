import time
import schedule
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

# Customizable Settings
REACTION_YES = "white_check_mark"  # ✅ in Slack reaction name format
REACTION_NO = "x"  # ❌ in Slack reaction name format
REMINDER_INTERVAL = 30  # Interval in minutes for reminders

# Slack Credentials (Set these in Railway.app or Render environment variables)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Initialize Slack Client
client = WebClient(token=SLACK_BOT_TOKEN)

# Dictionary to track users who haven't responded
pending_users = {}

def send_reminder_message():
    """ Sends the initial message in the channel. """
    try:
        response = client.chat_postMessage(
            channel=CHANNEL_ID,
            text="🔔 Did you punch in? React with ✅ for Yes, ❌ for No."
        )
        message_ts = response["ts"]  # Get the message timestamp to track reactions
        pending_users[message_ts] = []  # Store users who haven't responded
        print(f"Reminder sent at {message_ts}")

        # Schedule response check after REMINDER_INTERVAL
        schedule.every(REMINDER_INTERVAL).minutes.do(check_responses, message_ts).tag(message_ts)

    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

def check_responses(message_ts):
    """ Checks who has reacted and reminds only those who haven't. """
    try:
        reactions = client.reactions_get(channel=CHANNEL_ID, timestamp=message_ts)
        users_who_reacted = set()

        for reaction in reactions["message"].get("reactions", []):
            if reaction["name"] in [REACTION_YES, REACTION_NO]:  # Track only set reactions
                users_who_reacted.update(reaction["users"])

        # Get the list of all channel members
        members = client.conversations_members(channel=CHANNEL_ID)["members"]

        # Find users who haven't reacted
        bot_id = client.auth_test()["user_id"]  # Get bot user ID
        users_to_remind = set(members) - users_who_reacted - {bot_id}

        if users_to_remind:
            for user in users_to_remind:
                send_dm_reminder(user)
        else:
            schedule.clear(message_ts)  # Stop further reminders if everyone responded

    except SlackApiError as e:
        print(f"Error checking responses: {e.response['error']}")

def send_dm_reminder(user_id):
    """ Sends a direct message reminder to the user. """
    try:
        current_hour = int(time.strftime("%H"))
        reminder_text = (
            "⏰ You still haven’t punched in. Please do it now!" 
            if current_hour < 19 else 
            "⏰ You still haven’t punched out. Please do it now!"
        )

        client.chat_postMessage(channel=user_id, text=reminder_text)
        print(f"Reminder sent to {user_id}")

    except SlackApiError as e:
        print(f"Error sending DM: {e.response['error']}")

# Schedule the bot to run at 10 AM and 7 PM
schedule.every().monday.at("10:00").do(send_reminder_message)
schedule.every().monday.at("19:00").do(send_reminder_message)
schedule.every().tuesday.at("10:00").do(send_reminder_message)
schedule.every().tuesday.at("19:00").do(send_reminder_message)
schedule.every().wednesday.at("10:00").do(send_reminder_message)
schedule.every().wednesday.at("19:00").do(send_reminder_message)
schedule.every().thursday.at("10:00").do(send_reminder_message)
schedule.every().thursday.at("19:00").do(send_reminder_message)
schedule.every().friday.at("10:00").do(send_reminder_message)
schedule.every().friday.at("19:00").do(send_reminder_message)

# Keep the script running (for Render Background Worker)
while True:
    schedule.run_pending()
    time.sleep(60)
