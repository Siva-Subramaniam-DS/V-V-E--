import discord
from discord import app_commands
from discord.ext import commands
import random
from config.config import ORGANIZATION_NAME

class UtilitiesCog(commands.Cog, name="Utilities"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="maps", description="Randomly select 3, 5, or 7 maps for gameplay")
    @app_commands.describe(count="Number of maps to select (3, 5, or 7)")
    async def maps(self, interaction: discord.Interaction, count: int = 5):
        try:
            allowed_counts = [3, 5, 7]
            if count not in allowed_counts:
                await interaction.response.send_message("❌ Invalid number! Please select 3, 5, or 7.", ephemeral=True)
                return

            all_maps = [
                "Lost City", "Islands of Iceland", "Greenlands", "Monument Valley",
                "Arctic", "Storm", "Unexplored Rocks", "Two Samurai", "Mutant",
                "Monolith"
            ]
            selected_maps = random.sample(all_maps, count)
            
            embed = discord.Embed(
                title=f"🗺️ Selected Maps ({count})",
                description="\n".join([f"{i+1}. {m}" for i, m in enumerate(selected_maps)]),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"{ORGANIZATION_NAME} | Map Selector")
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="time", description="Get a random match time from fixed 30-min slots")
    async def time(self, interaction: discord.Interaction):
        try:
            hours = [12, 13, 14, 15, 16, 17]
            mins = [0, 30]
            rh = random.choice(hours)
            rm = random.choice(mins)
            formatted = f"{rh:02d}:{rm:02d} UTC"
            await interaction.response.send_message(f"⏰ **Random Match Time:** `{formatted}`")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(UtilitiesCog(bot))
