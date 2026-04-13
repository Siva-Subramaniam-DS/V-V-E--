import json, os, datetime, discord
from config.config import EVENTS_FILE, RULES_FILE











def get_current_rules():
    """Get current rules content"""
    return tournament_rules.get('rules', {}).get('content', '')

def load_rules():
    """Load rules from persistent storage"""
    global tournament_rules
    try:
        if os.path.exists('tournament_rules.json'):
            with open('tournament_rules.json', 'r', encoding='utf-8') as f:
                tournament_rules = json.load(f)
                print(f"Loaded tournament rules from file")
        else:
            tournament_rules = {}
            print("No existing rules file found, starting with empty rules")
    except Exception as e:
        print(f"Error loading tournament rules: {e}")
        tournament_rules = {}

def save_rules():
    """Save rules to persistent storage"""
    try:
        with open('tournament_rules.json', 'w', encoding='utf-8') as f:
            json.dump(tournament_rules, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving tournament rules: {e}")
        return False

async def display_rules(interaction: discord.Interaction):
    """Display current tournament rules in an embed"""
    try:
        global tournament_rules
        current_rules = get_current_rules()
        
        if not current_rules:
            embed = discord.Embed(
                title="📋 Tournament Rules",
                description="No tournament rules have been set yet.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="😈The Devil's Spot😈 Tournament System")
        else:
            embed = discord.Embed(
                title="📋 Tournament Rules",
                description=current_rules,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add metadata if available
            if 'rules' in tournament_rules and 'last_updated' in tournament_rules['rules']:
                updated_by = tournament_rules['rules'].get('updated_by', {}).get('username', 'Unknown')
                embed.set_footer(text=f"😈The Devil's Spot😈 • Last updated by {updated_by}")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    except Exception as e:
        print(f"Error displaying rules: {e}")
        await interaction.response.send_message("❌ An error occurred while displaying rules.", ephemeral=False)

