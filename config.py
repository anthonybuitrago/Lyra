import os
from dotenv import load_dotenv
load_dotenv()

# Discord Bot Token
TOKEN = os.getenv("DISCORD_TOKEN")

# Channel ID where the dashboard will live
MUSIC_CHANNEL_ID = 1444789327711174676

# Embed Colors
COLOR_MAIN = 0x9B59B6  # Purple
COLOR_ERROR = 0xE74C3C # Red
