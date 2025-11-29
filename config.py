import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Token
TOKEN = os.getenv("DISCORD_TOKEN")

# Channel ID where the dashboard will live
DASHBOARD_CHANNEL_ID = 1095897174878978050

# Spotify Credentials (Optional, but recommended for better matching)
SPOTIFY_CLIENT_ID = "YOUR_SPOTIFY_CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "YOUR_SPOTIFY_CLIENT_SECRET"

# Embed Colors
COLOR_MAIN = 0x9B59B6  # Purple
COLOR_ERROR = 0xE74C3C # Red
