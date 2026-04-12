import discord
from discord.ext import commands
import os

from config.config import load_config, ORGANIZATION_NAME

# Setup Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class TournamentBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        print("Loading Cogs...")
        # Load extensions (Cogs) dynamically
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('_'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"Loaded: {filename}")
        
        print("Syncing command tree globally...")
        await self.tree.sync()
        print("✅ Synced successfully.")

    async def on_ready(self):
        print(f"=====================================")
        print(f"👾 Bot is Online: {self.user.name}")
        print(f"🆔 Bot ID: {self.user.id}")
        print(f"🏢 Organization: {ORGANIZATION_NAME}")
        print(f"=====================================")

bot = TournamentBot()

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        for key, value in os.environ.items():
            if 'DISCORD' in key and 'TOKEN' in key:
                token = value
                break
    if not token:
        print("ERROR: DISCORD_TOKEN is missing from environment.")
        exit(1)
        
    bot.run(token, log_handler=None)
