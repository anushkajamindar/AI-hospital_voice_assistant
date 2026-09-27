"""
Places a test outbound call to your own phone so you can try the voice flow.
All values come from .env — never hard-code credentials in this file.

Add to .env:
    TEST_TO_NUMBER=+91XXXXXXXXXX   # the phone that should receive the test call
"""

import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
call = client.calls.create(
    to=os.environ["TEST_TO_NUMBER"],
    from_=os.environ["TWILIO_PHONE"],
    url=f"{os.environ['NGROK_URL'].rstrip('/')}/incoming-call",
)
print(call.sid)
