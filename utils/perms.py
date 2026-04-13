import discord
from config.config import ROLE_IDS

bot = None # Assigned dynamically at boot

def has_organizer_permission(interaction):
    """Check if user has organizer permissions for rule management"""
    head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
    return head_organizer_role is not None

def has_event_create_permission(interaction):
    """Check if user has permission to create events (Head Organizer, Head Helper or Helper Team)"""
    head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
    head_helper_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_helper"])
    helper_team_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["helper_team"])
    return head_organizer_role is not None or head_helper_role is not None or helper_team_role is not None

def has_event_result_permission(interaction):
    """Check if user has permission to post event results (Head Organizer or Judge)"""
    head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
    judge_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["judge"])
    return head_organizer_role is not None or judge_role is not None


