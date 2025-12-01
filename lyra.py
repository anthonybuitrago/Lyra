import discord
from discord.ext import commands
import config
import asyncio
import os

# Setup Intent
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

class LyraBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def on_ready(self):
        print(f'✅ Logged in as {self.user} (ID: {self.user.id})')
        print('➖ ------')

async def main():
    bot = LyraBot()
    
    # Load Cogs
    try:
        await bot.load_extension('cogs.music')
        print("📦 Loaded extension: cogs.music")
    except Exception as e:
        print(f"❌ Failed to load extension cogs.music: {e}")

    await bot.start(config.TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle graceful shutdown
        pass
