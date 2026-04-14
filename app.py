import discord
from discord import app_commands
from discord.ext import commands
import os
import random
from dotenv import load_dotenv
from itertools import combinations
from typing import Optional
import re
import datetime
import asyncio
import glob
from discord.ui import Button, View
import pytz
from PIL import Image, ImageDraw, ImageFont
# Removed pilmoji import due to dependency issues
import io
import json
from pathlib import Path
import requests
import tempfile
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# Firebase Setup
USE_FIREBASE = False
try:
    if os.path.exists("firebase_credentials.json"):
        if not firebase_admin._apps:
            cred = credentials.Certificate("firebase_credentials.json")
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        # "in firebase each bot as seperate collection so that they won't get confused"
        BOT_DOC = db.collection("Bots").document("Valorant_Vanguard_Esports")
        USE_FIREBASE = True
        print("Firebase initialized successfully.")
    else:
        print("firebase_credentials.json not found. Falling back to local JSON files.")
except Exception as e:
    print(f"Firebase initialization failed (falling back to local JSON): {e}")

# Default Configs — Ghost Fleet GR
DEFAULT_CHANNEL_IDS = {
    "take_schedule": 1493422902547185705,   # TAKE SCHEDULE
    "results": 1493422902547185705,         # MATCH RESULT (reuse take_schedule until dedicated is set)
    "transcript": 1493422861405388950,      # TOUR SUPPORT TICKET (transcript)
    "staff_attendance": 1493423298724233287, # ATTENDANCE
    "announcement": 1493371443445108857,    # DEADLINES channel (closest to announcement)
    "tour_chat": 1493422902547185705,       # Take schedule channel
    "registration": 1493371304860979434,    # RULES channel (placeholder)
    "rules": 1493371304860979434,           # RULES
    "bracket": 1493371371504275659,         # BRACKET
    "deadlines": 1493371443445108857,       # DEADLINE
    "participants_list": 1493371304860979434,
    "event_videos": 1493422902547185705,
    "category_1": 1493422365902897194,      # Category 1
    "category_2": 1493422524967686184,      # Category 2
    "closed_tickets_category": 1493423252658323598  # Closed Tickets
}

DEFAULT_ROLE_IDS = {
    "judge": 1493380731601424528,           # Tour Judge
    "recorder": 1493380303098740816,        # Tour Recorder
    "head_helper": 1493420982613053520,     # Tour helper
    "helper_team": 1493420982613053520,     # Tour helper
    "head_organizer": 1493380182285881354,  # Tour Organiser
    "staff": 1493380182285881354            # Staff (fallback to organiser)
}

CHANNEL_IDS = DEFAULT_CHANNEL_IDS.copy()
ROLE_IDS = DEFAULT_ROLE_IDS.copy()

# Bot Owner ID for special permissions
BOT_OWNER_ID = 1251442077561131059

# Branding constants — Ghost Fleet GR
ORGANIZATION_NAME = "Ghost Fleet GR"
TOURNAMENT_SYSTEM_NAME = "Ghost Fleet GR Tournament System"
BRACKET_LINK = "https://discord.com/channels/1084589736917737522/1493371371504275659"
BRACKET_API_KEY = ""
GOOGLE_SHEET_LINK = ""
CURRENT_TOURNAMENT_NAME = ""

# Key channel links for embeds
LINK_BRACKET = "https://discord.com/channels/1084589736917737522/1493371371504275659"
LINK_DEADLINE = "https://discord.com/channels/1084589736917737522/1493371443445108857"
LINK_RULES = "https://discord.com/channels/1084589736917737522/1493371304860979434"

# Ghost Fleet GR brand colour (deep navy blue)
BRAND_COLOR = 0x1E3A5F

def load_config():
    global CHANNEL_IDS, ROLE_IDS, ORGANIZATION_NAME, TOURNAMENT_SYSTEM_NAME, BRACKET_LINK, BRACKET_API_KEY, GOOGLE_SHEET_LINK, CURRENT_TOURNAMENT_NAME
    
    config = {}
    if USE_FIREBASE:
        try:
            doc = BOT_DOC.collection("Config").document("bot_config").get()
            if doc.exists:
                config = doc.to_dict()
                print("Loaded bot configurations from Firebase.")
        except Exception as e:
            print(f"Error loading config from Firebase: {e}")
    elif os.path.exists('bot_config.json'):
        try:
            with open('bot_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                print("Loaded bot configurations from bot_config.json")
        except Exception as e:
            print(f"Error loading config: {e}")
            
    if config:
        CHANNEL_IDS.update(config.get('channel_ids', {}))
        ROLE_IDS.update(config.get('role_ids', {}))
        ORGANIZATION_NAME = config.get('organization_name', ORGANIZATION_NAME)
        TOURNAMENT_SYSTEM_NAME = config.get('tournament_system_name', TOURNAMENT_SYSTEM_NAME)
        BRACKET_LINK = config.get('bracket_link', BRACKET_LINK)
        BRACKET_API_KEY = config.get('bracket_api_key', BRACKET_API_KEY)
        GOOGLE_SHEET_LINK = config.get('google_sheet_link', GOOGLE_SHEET_LINK)
        CURRENT_TOURNAMENT_NAME = config.get('current_tournament_name', "")

def save_config():
    config = {
        'channel_ids': CHANNEL_IDS,
        'role_ids': ROLE_IDS,
        'organization_name': ORGANIZATION_NAME,
        'tournament_system_name': TOURNAMENT_SYSTEM_NAME,
        'bracket_link': BRACKET_LINK,
        'bracket_api_key': BRACKET_API_KEY,
        'google_sheet_link': GOOGLE_SHEET_LINK,
        'current_tournament_name': CURRENT_TOURNAMENT_NAME
    }
    
    if USE_FIREBASE:
        try:
            BOT_DOC.collection("Config").document("bot_config").set(config)
            print("Saved bot configurations to Firebase")
        except Exception as e:
            print(f"Error saving config to Firebase: {e}")
    else:
        try:
            with open('bot_config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            print("Saved bot configurations to bot_config.json")
        except Exception as e:
            print(f"Error saving config: {e}")

# Load configuration on initialization
load_config()

# Set Windows event loop policy for asyncio
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Store scheduled events for reminders
scheduled_events = {}

# Store staff statistics for leaderboard
staff_stats = {}


# Load scheduled events from file on startup
def load_scheduled_events():
    global scheduled_events
    try:
        if os.path.exists('scheduled_events.json'):
            with open('scheduled_events.json', 'r') as f:
                data = json.load(f)
                # Convert datetime strings back to datetime objects
                for event_id, event_data in data.items():
                    if 'datetime' in event_data:
                        event_data['datetime'] = datetime.datetime.fromisoformat(event_data['datetime'])
                scheduled_events = data
                print(f"Loaded {len(scheduled_events)} scheduled events from file")
    except Exception as e:
        print(f"Error loading scheduled events: {e}")
        scheduled_events = {}

# Save scheduled events to file
def save_scheduled_events():
    try:
        # Convert datetime objects to strings for JSON serialization
        data_to_save = {}
        for event_id, event_data in scheduled_events.items():
            event_copy = event_data.copy()
            if 'datetime' in event_copy:
                event_copy['datetime'] = event_copy['datetime'].isoformat()
            
            # Convert Discord Member objects to IDs for JSON serialization
            if 'team1_captain' in event_copy and hasattr(event_copy['team1_captain'], 'id'):
                event_copy['team1_captain'] = event_copy['team1_captain'].id
            if 'team2_captain' in event_copy and hasattr(event_copy['team2_captain'], 'id'):
                event_copy['team2_captain'] = event_copy['team2_captain'].id
            if 'judge' in event_copy and hasattr(event_copy['judge'], 'id'):
                event_copy['judge'] = event_copy['judge'].id
            elif 'judge' in event_copy and event_copy['judge'] is None:
                event_copy['judge'] = None
                
            data_to_save[event_id] = event_copy
        
        with open('scheduled_events.json', 'w') as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving scheduled events: {e}")

# Track per-event reminder tasks (for cancellation/update)
reminder_tasks = {}

# Track per-event cleanup tasks (to remove finished events after result)
cleanup_tasks = {}

# Store judge assignments to prevent overloading
judge_assignments = {}  # {judge_id: [event_ids]}

import csv
import io

def extract_challonge_id(link: str) -> str:
    match = re.search(r'https?://(?:([a-zA-Z0-9-]+)\.)?challonge\.com/([a-zA-Z0-9-_]+)', link)
    if match:
        subdomain, path = match.groups()
        if subdomain and subdomain != 'www':
            return f"{subdomain}-{path}"
        return path
    return link.split('/')[-1]

def _sync_fetch_challonge_open_matches(bracket_link: str, api_key: str):
    """Synchronous version — call via asyncio.to_thread"""
    t_id = extract_challonge_id(bracket_link)
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    p_url = f"https://api.challonge.com/v1/tournaments/{t_id}/participants.json"
    p_req = requests.get(p_url, params={"api_key": api_key}, headers=headers, timeout=15)
    if p_req.status_code != 200:
        return None, f"Failed to fetch participants (HTTP {p_req.status_code}): {p_req.text[:300]}"
    pts = {p['participant']['id']: p['participant']['name'] for p in p_req.json()}
    m_url = f"https://api.challonge.com/v1/tournaments/{t_id}/matches.json"
    m_req = requests.get(m_url, params={"api_key": api_key, "state": "open"}, headers=headers, timeout=15)
    if m_req.status_code != 200:
        return None, f"Failed to fetch matches (HTTP {m_req.status_code}): {m_req.text[:300]}"
    matches_info = []
    for m in m_req.json():
        match = m['match']
        if not match.get('player1_id') or not match.get('player2_id'):
            continue
        p1 = pts.get(match['player1_id'], "TBD")
        p2 = pts.get(match['player2_id'], "TBD")
        matches_info.append({
            'id': match['id'],
            'round': match['round'],
            'team1': p1,
            'team2': p2,
            'player1_id': match['player1_id'],
            'player2_id': match['player2_id']
        })
    return matches_info, None

async def fetch_challonge_open_matches(bracket_link: str, api_key: str):
    """Async wrapper — runs the HTTP call in a thread so the event loop stays free."""
    return await asyncio.to_thread(_sync_fetch_challonge_open_matches, bracket_link, api_key)

def _sync_update_challonge_match(bracket_link: str, api_key: str, match_id: str, winner_id: str, scores_csv: str):
    """Synchronous version — call via asyncio.to_thread"""
    t_id = extract_challonge_id(bracket_link)
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    m_url = f"https://api.challonge.com/v1/tournaments/{t_id}/matches/{match_id}.json"
    data = {
        "api_key": api_key,
        "match[winner_id]": winner_id,
        "match[scores_csv]": scores_csv
    }
    resp = requests.put(m_url, data=data, headers=headers, timeout=15)
    if resp.status_code != 200:
        return False, resp.text
    return True, None

async def update_challonge_match(bracket_link: str, api_key: str, match_id: str, winner_id: str, scores_csv: str):
    """Async wrapper — runs the HTTP call in a thread so the event loop stays free."""
    return await asyncio.to_thread(_sync_update_challonge_match, bracket_link, api_key, match_id, winner_id, scores_csv)

def _sync_fetch_google_sheet_captains(sheet_link: str):
    """Synchronous version — call via asyncio.to_thread"""
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_link)
    if not match:
        return None, "Invalid Google Sheet link — could not extract sheet ID"
    sheet_id = match.group(1)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        reader = csv.reader(io.StringIO(resp.text))
        
        # Read header row
        h_row = next(reader, [])
        h_lower = [h.lower() for h in h_row]
        
        # Find which column contains the team name or discord name (Identifier)
        key_col = -1
        is_1v1 = False
        for i, h in enumerate(h_lower):
            if 'discord name' in h or 'participant' in h:
                key_col = i
                is_1v1 = True
                break
            elif 'team' in h:
                key_col = i
                is_1v1 = False
                break
                
        # Find which column contains the discord developer ID or mention (Value)
        val_col = -1
        for i, h in enumerate(h_lower):
            if 'developer id' in h or 'discord id' in h or 'mention' in h:
                val_col = i
                break
                
        # Default to columns 0 and 1 if nothing found
        if key_col == -1: key_col = 0
        if val_col == -1: val_col = 1
        
        captains = {}
        for row in reader:
            if len(row) > max(key_col, val_col):
                k = row[key_col].strip()
                v = row[val_col].strip()
                if k:
                    # If it's a raw discord number, format as ping <@>
                    if v.isdigit():
                        v = f"<@{v}>"
                    captains[k] = v
        return captains, is_1v1, None
    except Exception as e:
        return None, False, str(e)


async def fetch_google_sheet_captains(sheet_link: str):
    """Async wrapper — runs the HTTP call in a thread so the event loop stays free."""
    return await asyncio.to_thread(_sync_fetch_google_sheet_captains, sheet_link)

# ===========================================================================================
# RULE MANAGEMENT SYSTEM
# ===========================================================================================

# Store tournament rules in memory
tournament_rules = {}

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

def load_staff_stats():
    """Load staff statistics from persistence storage"""
    global staff_stats
    try:
        # Check for new staff_stats.json first
        if os.path.exists('staff_stats.json'):
            with open('staff_stats.json', 'r', encoding='utf-8') as f:
                staff_stats = json.load(f)
                print(f"Loaded staff statistics from staff_stats.json")
        # Legacy support: migrated from judge_stats.json if needed
        elif os.path.exists('judge_stats.json'):
            with open('judge_stats.json', 'r', encoding='utf-8') as f:
                legacy_stats = json.load(f)
                staff_stats = legacy_stats
                print(f"Migrated statistics from judge_stats.json")
                save_staff_stats()
        else:
            staff_stats = {}
            print("No existing staff stats file found")
    except Exception as e:
        print(f"Error loading staff stats: {e}")
        staff_stats = {}

def save_staff_stats():
    """Save staff statistics to persistent storage"""
    try:
        with open('staff_stats.json', 'w', encoding='utf-8') as f:
            json.dump(staff_stats, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving staff stats: {e}")
        return False

def reset_staff_stats():
    """Reset all staff statistics"""
    global staff_stats
    staff_stats = {}
    return save_staff_stats()

def update_staff_stats(user: discord.Member, role_type: str):
    """Update stats for a staff member (judge or recorder)"""
    global staff_stats
    user_id = str(user.id)
    
    if user_id not in staff_stats:
        staff_stats[user_id] = {
            "name": user.display_name,
            "judge_count": 0,
            "recorder_count": 0,
            "total_count": 0
        }
    
    # Update count based on role
    if role_type == "judge":
        staff_stats[user_id]["judge_count"] = staff_stats[user_id].get("judge_count", 0) + 1
    elif role_type == "recorder":
        staff_stats[user_id]["recorder_count"] = staff_stats[user_id].get("recorder_count", 0) + 1
        
    # Update total and metadata
    staff_stats[user_id]["total_count"] = staff_stats[user_id].get("judge_count", 0) + staff_stats[user_id].get("recorder_count", 0)
    staff_stats[user_id]["name"] = user.display_name
    staff_stats[user_id]["last_active"] = datetime.datetime.utcnow().isoformat()
    
    save_staff_stats()

def save_rules():
    """Save rules to persistent storage"""
    try:
        with open('tournament_rules.json', 'w', encoding='utf-8') as f:
            json.dump(tournament_rules, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving tournament rules: {e}")
        return False

def get_current_rules():
    """Get current rules content"""
    return tournament_rules.get('rules', {}).get('content', '')

def set_rules_content(content, user_id, username):
    """Set new rules content with metadata"""
    global tournament_rules
    
    # Sanitize content (basic cleanup)
    if content:
        content = content.strip()
    
    # Update rules with metadata
    tournament_rules['rules'] = {
        'content': content,
        'last_updated': datetime.datetime.utcnow().isoformat(),
        'updated_by': {
            'user_id': user_id,
            'username': username
        },
        'version': tournament_rules.get('rules', {}).get('version', 0) + 1
    }
    
    return save_rules()

# Command data structure for help system
COMMAND_DATA = {
    "system": {
        "title": "⚙️ System Commands",
        "description": "Basic bot functionality available to all users",
        "commands": [
            {
                "name": "/help",
                "description": "Display this comprehensive command guide with role-based filtering",
                "usage": "/help",
                "permissions": "everyone",
                "example": "Simply type `/help` to see available commands"
            },
            {
                "name": "/rules",
                "description": "View tournament rules (or manage them if you're an organizer)",
                "usage": "/rules",
                "permissions": "everyone (view) / organizer (manage)",
                "example": "Use `/rules` to view current tournament rules"
            }
        ]
    },
    "utility": {
        "title": "🛠️ Utility Commands",
        "description": "Helpful tools for tournament management",
        "commands": [
            {
                "name": "/team_balance",
                "description": "Balance two teams based on player skill levels",
                "usage": "/team_balance levels:<comma-separated levels>",
                "permissions": "everyone",
                "example": "Example: `/team_balance levels:48,50,51,35,51,50,50,37,51,52`"
            },
            {
                "name": "/time",
                "description": "Generate a random match time between 12:00-17:59 UTC",
                "usage": "/time",
                "permissions": "everyone",
                "example": "Use `/time` to get a random tournament match time"
            },
            {
                "name": "/choose",
                "description": "Make a random choice from comma-separated options",
                "usage": "/choose options:<option1,option2,option3>",
                "permissions": "everyone",
                "example": "Example: `/choose options:Map1,Map2,Map3` to randomly select a map"
            }
        ]
    },
    "event_management": {
        "title": "🏆 Event Management",
        "description": "Tournament event creation and management (requires special permissions)",
        "commands": [
            {
                "name": "/event-create",
                "description": "Create new tournament events with Group support and Winner/Loser options",
                "usage": "/event-create team_1_captain:<@user> team_2_captain:<@user> hour:<0-23> minute:<0-59> date:<1-31> month:<1-12> round:<round> tournament:<name> [group:<A-J/Winner/Loser>]",
                "permissions": "head_organizer / head_helper / helper_team",
                "example": "Example: `/event-create team_1_captain:@Captain1 team_2_captain:@Captain2 hour:15 minute:30 date:25 month:12 round:R1 tournament:Summer Cup group:Group A`",
                "round_options": "R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, 3rd Place, Final",
                "group_options": "Group A, Group B, Group C, Group D, Group E, Group F, Group G, Group H, Group I, Group J, Winner, Loser"
            },
            {
                "name": "/event-edit",
                "description": "Edit existing events to correct mistakes with Group support and Winner/Loser options",
                "usage": "/event-edit",
                "permissions": "head_organizer / head_helper / helper_team",
                "example": "Use `/event-edit` to select and modify any scheduled event with pre-filled current values including group assignments (Group A-J, Winner, Loser)"
            },
            {
                "name": "/event-result",
                "description": "Record match results with Group support and comprehensive tournament tracking",
                "usage": "/event-result winner:<@user> winner_score:<score> loser:<@user> loser_score:<score> tournament:<name> round:<round> [group:<A-J/Winner/Loser>] [remarks:<text>] [screenshots:<1-11>]",
                "permissions": "head_organizer / judge",
                "example": "Use `/event-result` to record match outcomes with group information and screenshot evidence",
                "round_options": "R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, 3rd Place, Final",
                "group_options": "Group A, Group B, Group C, Group D, Group E, Group F, Group G, Group H, Group I, Group J, Winner, Loser"
            },
            {
                "name": "/event-delete",
                "description": "Delete scheduled events (use with caution)",
                "usage": "/event-delete",
                "permissions": "head_organizer / head_helper / helper_team",
                "example": "Use `/event-delete` and select from scheduled events to remove"
            },
            {
                "name": "/unassigned_events",
                "description": "List all events without a judge assigned for easy management",
                "usage": "/unassigned_events",
                "permissions": "head_organizer / head_helper / helper_team / judge",
                "example": "Use `/unassigned_events` to see which matches still need judges"
            },
            {
                "name": "/exchange",
                "description": "Exchange a Judge or Recorder for events in current channel",
                "usage": "/exchange role:[Judge/Recorder] old_user:<@user> new_user:<@user>",
                "permissions": "head_organizer / head_helper / helper_team / judge",
                "example": "Use `/exchange` to reassign staff for events in the current channel"
            },
            {
                "name": "/staff-update",
                "description": "Update a staff member's match count in the leaderboard",
                "usage": "/staff-update staff_member:<@user> role:[Judge/Recorder] action:[Add/Subtract/Set] amount:<number>",
                "permissions": "head_organizer",
                "example": "Use `/staff-update` to manually correct staff leaderboard statistics"
            },
            {
                "name": "/tournament-setup",
                "description": "Wipe all old data and set up for a new tournament",
                "usage": "/tournament-setup [bracket_link:<url>]",
                "permissions": "bot_owner",
                "example": "Use `/tournament-setup` to start a new tournament season (Bot Owner Only)"
            }
        ]
    },
    "judge": {
        "title": "👨‍⚖️ Judge Commands",
        "description": "Special commands for tournament judges",
        "commands": [
            {
                "name": "Take Schedule Button",
                "description": "Click the 'Take Schedule' button on event posts to assign yourself as judge",
                "usage": "Click button on event announcements",
                "permissions": "judge / head_organizer",
                "example": "Look for green 'Take Schedule' buttons in the schedule channel"
            },
            {
                "name": "/event-result",
                "description": "Record official match results with Group support and comprehensive tracking",
                "usage": "/event-result winner:<@user> winner_score:<score> loser:<@user> loser_score:<score> tournament:<name> round:<round> [group:<A-J>] [remarks:<text>] [screenshots:<1-11>]",
                "permissions": "judge / head_organizer",
                "example": "Use after completing a match you judged to record the official result with group information and evidence",
                "round_options": "R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, Qualifier, Semi Final, 3rd Place, Final",
                "group_options": "Group A, Group B, Group C, Group D, Group E, Group F, Group G, Group H, Group I, Group J"
            },
            {
                "name": "/unassigned_events",
                "description": "View events without assigned judges to help with scheduling",
                "usage": "/unassigned_events",
                "permissions": "judge / head_organizer",
                "example": "Use `/unassigned_events` to see which matches need judges"
            }
        ]
    }
}

def get_user_permission_level(user_roles, user_id: int = None) -> str:
    """Determine user's permission level based on their Discord roles"""
    try:
        # Bot owner ALWAYS gets owner level regardless of roles
        if user_id and user_id == BOT_OWNER_ID:
            return "owner"
        
        role_ids = [role.id for role in user_roles]
        
        if ROLE_IDS["head_organizer"] in role_ids:
            return "organizer"
        elif ROLE_IDS["head_helper"] in role_ids or ROLE_IDS["helper_team"] in role_ids:
            return "helper"
        elif ROLE_IDS["judge"] in role_ids:
            return "judge"
        elif ROLE_IDS["recorder"] in role_ids:
            return "recorder"
        else:
            return "user"
    except Exception as e:
        print(f"Error determining user permission level: {e}")
        return "user"  # Default to basic user permissions

def filter_commands_by_permission(permission_level: str) -> dict:
    """Filter command data based on user's permission level"""
    try:
        filtered_data = {}
        
        # Always include system and utility commands for everyone
        filtered_data["system"] = COMMAND_DATA["system"]
        filtered_data["utility"] = COMMAND_DATA["utility"]
        
        # Add role-specific commands based on permission level
        if permission_level in ["owner", "organizer", "helper"]:
            # Owners, organizers and helpers get all commands
            filtered_data["event_management"] = COMMAND_DATA["event_management"]
            filtered_data["judge"] = COMMAND_DATA["judge"]
        elif permission_level == "judge":
            # Judges get judge commands and can see some event management
            filtered_data["judge"] = COMMAND_DATA["judge"]
            # Show limited event management (only event-result)
            judge_event_commands = {
                "title": "🏆 Event Management (Judge Access)",
                "description": "Event commands available to judges",
                "commands": [cmd for cmd in COMMAND_DATA["event_management"]["commands"] 
                           if cmd["name"] == "/event-result"]
            }
            if judge_event_commands["commands"]:
                filtered_data["event_management"] = judge_event_commands
        
        return filtered_data
    except Exception as e:
        print(f"Error filtering commands by permission: {e}")
        # Return basic commands as fallback
        return {
            "system": COMMAND_DATA["system"],
            "utility": COMMAND_DATA["utility"]
        }

def build_help_embed(permission_level: str, user_name: str, bot_icon_url: str = None, user_icon_url: str = None) -> discord.Embed:
    """Build a comprehensive help embed based on user's permission level — Ghost Fleet GR styled"""
    try:
        filtered_commands = filter_commands_by_permission(permission_level)

        # Permission-level badge with emoji
        badge_map = {
            "owner":     "👑 Bot Owner",
            "organizer": "🏛️ Organiser",
            "helper":    "🛡️ Helper",
            "judge":     "⚖️ Judge",
            "recorder":  "🎥 Recorder",
            "user":      "👤 Member",
        }
        badge = badge_map.get(permission_level, "👤 Member")

        embed = discord.Embed(
            title=f"📖 Ghost Fleet GR — Command Centre",
            description=(
                f"**{TOURNAMENT_SYSTEM_NAME}**\n"
                f"───────────────────────────\n"
                f"🔰 **Access Level:** {badge}\n"
                f"📌 **Bracket:** [View Live Bracket]({LINK_BRACKET})\n"
                f"📅 **Deadlines:** [View Schedule]({LINK_DEADLINE})\n"
                f"📜 **Rules:** [Read Rules]({LINK_RULES})"
            ),
            color=discord.Color(BRAND_COLOR),
            timestamp=discord.utils.utcnow()
        )

        if bot_icon_url:
            embed.set_thumbnail(url=bot_icon_url)

        # Add command categories
        for category_key, category_data in filtered_commands.items():
            commands_text = ""
            for cmd in category_data["commands"]:
                commands_text += f"`{cmd['name']}`  — {cmd['description']}\n"
                commands_text += f"   ┣ 🔒 *{cmd['permissions']}*\n"
                if cmd.get('example'):
                    commands_text += f"   ┗ 💡 *{cmd['example']}*\n"
                else:
                    commands_text += "\n"

            # Chunk if over Discord field limit
            if len(commands_text) > 1024:
                parts, current_part = [], ""
                for line in commands_text.split('\n'):
                    if len(current_part + line + '\n') > 1024:
                        parts.append(current_part.strip())
                        current_part = line + '\n'
                    else:
                        current_part += line + '\n'
                if current_part.strip():
                    parts.append(current_part.strip())
                for i, part in enumerate(parts):
                    fname = category_data["title"] if i == 0 else f"{category_data['title']} (cont.)"
                    embed.add_field(name=fname, value=part, inline=False)
            else:
                embed.add_field(name=category_data["title"], value=commands_text, inline=False)

        footer_text = f"{ORGANIZATION_NAME} • Help • {user_name}"
        if user_icon_url:
            embed.set_footer(text=footer_text, icon_url=user_icon_url)
        else:
            embed.set_footer(text=footer_text)
        return embed

    except Exception as e:
        print(f"Error building help embed: {e}")
        embed = discord.Embed(
            title="📖 Command Guide",
            description="Error loading command information. Please try again.",
            color=discord.Color(BRAND_COLOR),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{ORGANIZATION_NAME}")
        return embed

def has_organizer_permission(interaction):
    """Check if user has organizer permissions for rule management"""
    head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
    return head_organizer_role is not None

# Embed field utility functions for safe Discord.py embed manipulation
def find_field_index(embed: discord.Embed, field_name: str) -> int:
    """Find the index of a field by name. Returns -1 if not found."""
    try:
        for i, field in enumerate(embed.fields):
            if field.name == field_name:
                return i
        return -1
    except Exception as e:
        print(f"Error finding field index: {e}")
        return -1

def remove_field_by_name(embed: discord.Embed, field_name: str) -> bool:
    """Safely remove a field by name using Discord.py methods. Returns True if removed, False if not found."""
    try:
        field_index = find_field_index(embed, field_name)
        if field_index != -1:
            embed.remove_field(field_index)
            return True
        return False
    except Exception as e:
        print(f"Error removing field by name '{field_name}': {e}")
        return False

def update_judge_field(embed: discord.Embed, judge_member: discord.Member) -> bool:
    """Update or add judge field safely. Returns True if successful."""
    try:
        # Remove existing judge field if it exists
        remove_field_by_name(embed, "👨‍⚖️ Judge")
        
        # Add new judge field
        embed.add_field(
            name="👨‍⚖️ Judge", 
            value=f"{judge_member.mention}", 
            inline=True
        )
        return True
    except Exception as e:
        print(f"Error updating judge field: {e}")
        return False

def remove_judge_field(embed: discord.Embed) -> bool:
    """Remove judge field safely. Returns True if removed, False if not found."""
    try:
        return remove_field_by_name(embed, "👨‍⚖️ Judge")
    except Exception as e:
        print(f"Error removing judge field: {e}")
        return False

def add_green_circle_to_title(title: str) -> str:
    """Add green circle emoji to the beginning of title if not already present"""
    green_circle = "🟢"
    
    # Check if already has green circle
    if title and title.startswith(green_circle):
        return title
    
    # Add green circle to beginning
    return green_circle + (title or "")

def update_embed_title_with_green_circle(embed: discord.Embed) -> bool:
    """Update embed title with green circle, returns success status"""
    try:
        if embed.title:
            new_title = add_green_circle_to_title(embed.title)
            embed.title = new_title
            return True
        return False
    except Exception as e:
        print(f"Error updating embed title with green circle: {e}")
        return False

def replace_green_circle_with_checkmark(title: str) -> str:
    """Replace green circle emoji with checkmark emoji in title"""
    green_circle = "🟢"
    checkmark = "✅"
    
    if title and title.startswith(green_circle):
        return checkmark + title[len(green_circle):]
    
    # If no green circle, just add checkmark at the beginning
    return checkmark + (title or "")

def update_embed_title_with_checkmark(embed: discord.Embed) -> bool:
    """Update embed title with checkmark, returns success status"""
    try:
        if embed.title:
            new_title = replace_green_circle_with_checkmark(embed.title)
            embed.title = new_title
            return True
        return False
    except Exception as e:
        print(f"Error updating embed title with checkmark: {e}")
        return False

def can_judge_take_schedule(judge_id: int, max_assignments: int = 3) -> tuple[bool, str]:
    """Check if a judge can take another schedule"""
    if judge_id not in judge_assignments:
        return True, ""
    
    current_assignments = len(judge_assignments[judge_id])
    if current_assignments >= max_assignments:
        return False, f"You already have {current_assignments} schedule(s) assigned. Maximum allowed is {max_assignments}."
    
    return True, ""

def add_judge_assignment(judge_id: int, event_id: str):
    """Add a schedule assignment to a judge"""
    if judge_id not in judge_assignments:
        judge_assignments[judge_id] = []
    judge_assignments[judge_id].append(event_id)

def remove_judge_assignment(judge_id: int, event_id: str):
    """Remove a schedule assignment from a judge"""
    if judge_id in judge_assignments and event_id in judge_assignments[judge_id]:
        judge_assignments[judge_id].remove(event_id)
        if not judge_assignments[judge_id]:  # Remove empty list
            del judge_assignments[judge_id]

class TakeScheduleButton(View):
    def __init__(self, event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, event_channel: discord.TextChannel = None):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.team1_captain = team1_captain
        self.team2_captain = team2_captain
        self.event_channel = event_channel
        self.judge = None
        self._taking_schedule = False  # Flag to prevent race conditions
        
    @discord.ui.button(label="Take Schedule", style=discord.ButtonStyle.green, emoji="📋")
    async def take_schedule(self, interaction: discord.Interaction, button: Button):
        # Prevent race conditions by checking if someone is already taking the schedule
        if self._taking_schedule:
            await interaction.response.send_message("⏳ Another judge is currently taking this schedule. Please wait a moment.", ephemeral=True)
            return
            
        # Check if user has Judge or Head Organizer role
        head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
        judge_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["judge"])
        if not (head_organizer_role or judge_role):
            await interaction.response.send_message("❌ You need **Head Organizer** or **Judge** role to take this schedule.", ephemeral=True)
            return
            
        # Check if already taken
        if self.judge:
            await interaction.response.send_message(f"❌ This schedule has already been taken by {self.judge.display_name}.", ephemeral=True)
            return
        
        # Check if judge can take more schedules
        can_take, error_message = can_judge_take_schedule(interaction.user.id, max_assignments=3)
        if not can_take:
            await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)
            return
        
        # Set flag to prevent race conditions
        self._taking_schedule = True
        
        try:
            # Defer response to give us time to process
            await interaction.response.defer(ephemeral=True)
            
            # Double-check if still available (in case another judge took it while we were processing)
            if self.judge:
                await interaction.followup.send(f"❌ This schedule has already been taken by {self.judge.display_name}.", ephemeral=True)
                return
            
            # Assign judge
            self.judge = interaction.user
            
            # Add to judge assignments tracking
            add_judge_assignment(interaction.user.id, self.event_id)
            
            # Update button appearance
            button.label = f"Taken by {interaction.user.display_name}"
            button.style = discord.ButtonStyle.gray
            button.disabled = True
            button.emoji = "✅"
            
            # Update the embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            
            # Update judge field using safe utility function
            if not update_judge_field(embed, interaction.user):
                await interaction.followup.send("❌ Failed to update embed with judge information.", ephemeral=True)
                return
            
            # Update the message with the updated take button only
            await interaction.message.edit(embed=embed, view=self)
            
            # Send success message
            await interaction.followup.send("✅ You have successfully taken this schedule!", ephemeral=True)
            
            # Send notification to the event channel
            await self.send_judge_assignment_notification(interaction.user)
            
            # Update scheduled events with judge
            if self.event_id in scheduled_events:
                scheduled_events[self.event_id]['judge'] = self.judge
            
        except Exception as e:
            # Reset flag in case of error
            self._taking_schedule = False
            print(f"Error in take_schedule: {e}")
            await interaction.followup.send(f"❌ An error occurred while taking the schedule: {str(e)}", ephemeral=True)
        finally:
            # Reset flag after processing
            self._taking_schedule = False

    
    async def send_judge_assignment_notification(self, judge: discord.Member):
        """Send notification to the event channel when a judge is assigned and add judge to channel"""
        if not self.event_channel:
            return
        
        try:
            # Add judge to the event channel with proper permissions
            await self.event_channel.set_permissions(
                judge, 
                read_messages=True, 
                send_messages=True, 
                view_channel=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True
            )
            
            # Create notification embed
            embed = discord.Embed(
                title="👨‍⚖️ Judge Assigned",
                description=f"**{judge.display_name}** has been assigned as the judge for this match!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📋 Match Details",
                value=f"**Team 1:** {self.team1_captain.mention}\n**Team 2:** {self.team2_captain.mention}",
                inline=False
            )
            
            embed.add_field(
                name="👨‍⚖️ Judge",
                value=f"{judge.mention}\n✅ **Added to channel**",
                inline=True
            )
            
            embed.set_footer(text=f"Judge Assignment • {ORGANIZATION_NAME}")
            
            # Send notification to the event channel
            await self.event_channel.send(
                content=f"🔔 {judge.mention} {self.team1_captain.mention} {self.team2_captain.mention}",
                embed=embed
            )
            
        except discord.Forbidden:
            print(f"Error: Bot doesn't have permission to add {judge.display_name} to channel {self.event_channel.name}")
        except Exception as e:
            print(f"Error sending judge assignment notification: {e}")
    
    





# ===========================================================================================
# RULE MANAGEMENT UI COMPONENTS
# ===========================================================================================

class RuleInputModal(discord.ui.Modal):
    """Modal for entering/editing rule content"""
    
    def __init__(self, title: str, current_content: str = ""):
        super().__init__(title=title)
        
        # Text input field for rule content
        self.rule_input = discord.ui.TextInput(
            label="Tournament Rules",
            placeholder="Enter the tournament rules here...",
            default=current_content,
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=False
        )
        self.add_item(self.rule_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the content from the input
            content = self.rule_input.value.strip()
            
            # Save the rules
            success = set_rules_content(content, interaction.user.id, interaction.user.name)
            
            if success:
                # Create confirmation embed
                embed = discord.Embed(
                    title="✅ Rules Updated Successfully",
                    description="Tournament rules have been saved.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                if content:
                    # Show preview of rules (truncated if too long)
                    preview = content[:500] + "..." if len(content) > 500 else content
                    embed.add_field(name="Rules Preview", value=f"```\n{preview}\n```", inline=False)
                else:
                    embed.add_field(name="Status", value="Rules have been cleared (empty)", inline=False)
                
                embed.set_footer(text=f"Updated by {interaction.user.name}")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Failed to save rules. Please try again.", ephemeral=True)
                
        except Exception as e:
            print(f"Error in rule modal submission: {e}")
            await interaction.response.send_message("❌ An error occurred while saving rules.", ephemeral=True)

class RulesManagementView(discord.ui.View):
    """Interactive view for organizers with rule management buttons"""
    
    def __init__(self):
        super().__init__(timeout=300)  # 5 minute timeout
    
    @discord.ui.button(label="Enter Rules", style=discord.ButtonStyle.green, emoji="📝")
    async def enter_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to enter new rules"""
        modal = RuleInputModal("Enter Tournament Rules")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Reedit Rules", style=discord.ButtonStyle.primary, emoji="✏️")
    async def reedit_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit existing rules"""
        current_rules = get_current_rules()
        
        if not current_rules:
            await interaction.response.send_message("❌ No rules are currently set. Use 'Enter Rules' to create new rules.", ephemeral=True)
            return
        
        modal = RuleInputModal("Edit Tournament Rules", current_rules)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Show Rules", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def show_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to display current rules"""
        await display_rules(interaction)

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
            embed.set_footer(text=f"{ORGANIZATION_NAME} • Tournament System")
        else:
            embed = discord.Embed(
                title="📋 Tournament Rules",
                description=current_rules,
                color=discord.Color(BRAND_COLOR),
                timestamp=discord.utils.utcnow()
            )
            
            # Add metadata if available
            if 'rules' in tournament_rules and 'last_updated' in tournament_rules['rules']:
                updated_by = tournament_rules['rules'].get('updated_by', {}).get('username', 'Unknown')
                embed.set_footer(text=f"{ORGANIZATION_NAME} • Last updated by {updated_by}")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    except Exception as e:
        print(f"Error displaying rules: {e}")
        await interaction.response.send_message("❌ An error occurred while displaying rules.", ephemeral=False)

class JudgeLeaderboardView(View):
    """View for staff leaderboard with reset functionality"""
    
    def __init__(self, show_reset: bool = False):
        super().__init__(timeout=300)
        self.show_reset = show_reset
        
        if not show_reset:
            self.clear_items()
    
    @discord.ui.button(label="🔄 Reset Leaderboard", style=discord.ButtonStyle.danger, emoji="🔄")
    async def reset_leaderboard(self, interaction: discord.Interaction, button: Button):
        # Double-check permissions
        head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
        if not head_organizer_role:
            await interaction.response.send_message("❌ You need **Head Organizer** role to reset the leaderboard.", ephemeral=True)
            return
        
        confirm_view = ConfirmResetView()
        await interaction.response.send_message(
            "⚠️ **WARNING**: This will permanently delete all staff statistics!\n\n"
            "Are you sure you want to reset the staff leaderboard?",
            view=confirm_view,
            ephemeral=True
        )

class ConfirmResetView(View):
    """Confirmation view for resetting staff leaderboard"""
    
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="✅ Yes, Reset", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_reset(self, interaction: discord.Interaction, button: Button):
        try:
            reset_staff_stats()
            await interaction.response.edit_message(
                content="✅ **Staff leaderboard has been reset successfully!**",
                view=None
            )
            print(f"Staff leaderboard reset by {interaction.user.display_name}")
        except Exception as e:
            print(f"Error resetting staff leaderboard: {e}")
            await interaction.response.edit_message(
                content="❌ **Error resetting leaderboard.**",
                view=None
            )
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content="✅ **Reset cancelled.**",
            view=None
        )

# ===========================================================================================
# NOTIFICATION AND REMINDER SYSTEM (Ten-minute reminder for captains and judge)
# ===========================================================================================

async def send_ten_minute_reminder(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel, match_time: datetime.datetime):
    """Send 10-minute reminder notification to judge and captains"""
    try:
        if not event_channel:
            print(f"No event channel provided for event {event_id}")
            return

        # Get the latest data from scheduled_events if available
        resolved_judge = judge
        resolved_team1_captain = team1_captain
        resolved_team2_captain = team2_captain
        
        if event_id in scheduled_events:
            event_data = scheduled_events[event_id]
            stored_judge = event_data.get('judge')
            if stored_judge:
                resolved_judge = stored_judge
            
            # Get updated captain information
            stored_team1 = event_data.get('team1_captain')
            stored_team2 = event_data.get('team2_captain')
            if stored_team1:
                resolved_team1_captain = stored_team1
            if stored_team2:
                resolved_team2_captain = stored_team2

        # Create reminder embed
        embed = discord.Embed(
            title="⏰ 10-MINUTE MATCH REMINDER",
            description=f"**Your tournament match is starting in 10 minutes!**",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🕒 Match Time", value=f"<t:{int(match_time.timestamp())}:F>", inline=False)
        embed.add_field(name="👥 Team Captains", value=f"<@{resolved_team1_captain.id}> vs <@{resolved_team2_captain.id}>", inline=False)
        if resolved_judge:
            embed.add_field(name="👨‍⚖️ Judge", value=f"<@{resolved_judge.id}>", inline=False)
        embed.add_field(name="� ActAion Required", value="Please prepare for the match and join the designated channel.", inline=False)
        embed.set_footer(text="Tournament Management System")

        # Send notification with pings
        pings = f"<@{resolved_team1_captain.id}> <@{resolved_team2_captain.id}>"
        if resolved_judge:
            pings = f"<@{resolved_judge.id}> " + pings
        notification_text = f"🔔 **MATCH REMINDER**\n\n{pings}\n\nYour match starts in **10 minutes**!"

        await event_channel.send(content=notification_text, embed=embed)
        print(f"10-minute reminder sent for event {event_id}")
    except Exception as e:
        print(f"Error sending 10-minute reminder for event {event_id}: {e}")


async def schedule_ten_minute_reminder(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel, match_time: datetime.datetime):
    """Schedule a 10-minute reminder for the match"""
    try:
        # Calculate when to send the 10-minute reminder
        reminder_time = match_time - datetime.timedelta(minutes=10)
        now = datetime.datetime.now(pytz.UTC)

        # Ensure match_time and reminder_time are timezone-aware UTC
        if match_time.tzinfo is None:
            match_time = match_time.replace(tzinfo=pytz.UTC)
            reminder_time = match_time - datetime.timedelta(minutes=10)

        # Check if reminder time is in the future
        if reminder_time <= now:
            print(f"Reminder time for event {event_id} is in the past, skipping")
            return

        # Calculate delay in seconds
        delay_seconds = (reminder_time - now).total_seconds()

        async def reminder_task():
            try:
                await asyncio.sleep(delay_seconds)
                await send_ten_minute_reminder(event_id, team1_captain, team2_captain, judge, event_channel, match_time)
            except asyncio.CancelledError:
                print(f"Reminder task for event {event_id} was cancelled")
            except Exception as e:
                print(f"Error in reminder task for event {event_id}: {e}")

        # Cancel existing reminder if any
        if event_id in reminder_tasks:
            reminder_tasks[event_id].cancel()

        # Schedule new reminder
        reminder_tasks[event_id] = asyncio.create_task(reminder_task())
        print(f"10-minute reminder scheduled for event {event_id} at {reminder_time}")
    except Exception as e:
        print(f"Error scheduling 10-minute reminder for event {event_id}: {e}")


async def schedule_event_reminder_v2(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel):
    """Schedule event reminder with 10-minute notification using stored event datetime"""
    try:
        if event_id not in scheduled_events:
            print(f"Event {event_id} not found in scheduled_events")
            return
        event_data = scheduled_events[event_id]
        match_time = event_data.get('datetime')
        if not match_time:
            print(f"No datetime found for event {event_id}")
            return
        # Ensure timezone-aware UTC
        if match_time.tzinfo is None:
            match_time = match_time.replace(tzinfo=pytz.UTC)
        await schedule_ten_minute_reminder(event_id, team1_captain, team2_captain, judge, event_channel, match_time)
    except Exception as e:
        print(f"Error in schedule_event_reminder_v2 for event {event_id}: {e}")

async def schedule_event_cleanup(event_id: str, delay_hours: int = 36):
    """Schedule cleanup to remove an event after delay_hours (default 36h)."""
    try:
        if event_id not in scheduled_events:
            return
        delay_seconds = delay_hours * 3600

        async def cleanup_task():
            try:
                await asyncio.sleep(delay_seconds)
                data = scheduled_events.get(event_id)
                if not data:
                    return
                # Delete original schedule message if known
                try:
                    guilds = bot.guilds
                    for guild in guilds:
                        ch_id = data.get('schedule_channel_id')
                        msg_id = data.get('schedule_message_id')
                        if ch_id and msg_id:
                            channel = guild.get_channel(ch_id)
                            if channel:
                                try:
                                    msg = await channel.fetch_message(msg_id)
                                    await msg.delete()
                                except discord.NotFound:
                                    pass
                                except Exception as e:
                                    print(f"Error deleting schedule message for {event_id}: {e}")
                except Exception as e:
                    print(f"Guild/channel fetch error during cleanup for {event_id}: {e}")

                # Clean up poster file if any
                try:
                    poster_path = data.get('poster_path')
                    if poster_path and os.path.exists(poster_path):
                        os.remove(poster_path)
                except Exception as e:
                    print(f"Poster cleanup error for {event_id}: {e}")

                # Remove any reminder task
                try:
                    if event_id in reminder_tasks:
                        reminder_tasks[event_id].cancel()
                        del reminder_tasks[event_id]
                except Exception:
                    pass

                # Finally remove from scheduled events and persist
                try:
                    if event_id in scheduled_events:
                        del scheduled_events[event_id]
                        save_scheduled_events()
                except Exception as e:
                    print(f"Error removing event {event_id} in cleanup: {e}")
            except asyncio.CancelledError:
                print(f"Cleanup task for event {event_id} was cancelled")
            except Exception as e:
                print(f"Error in cleanup task for event {event_id}: {e}")

        # Cancel existing cleanup if any and schedule new
        if event_id in cleanup_tasks:
            try:
                cleanup_tasks[event_id].cancel()
            except Exception:
                pass

        cleanup_tasks[event_id] = asyncio.create_task(cleanup_task())
        print(f"Cleanup scheduled for event {event_id} in {delay_hours} hours")
    except Exception as e:
        print(f"Error scheduling cleanup for event {event_id}: {e}")

# Google Fonts API Integration
def download_google_font(font_family: str, font_style: str = "regular", font_weight: str = "400") -> str:
    """Download a font from Google Fonts API and return the local file path"""
    try:
        # Google Fonts API URL
        api_url = f"https://fonts.googleapis.com/css2?family={font_family.replace(' ', '+')}:wght@{font_weight}"
        
        # Add style parameter if not regular
        if font_style != "regular":
            api_url += f"&style={font_style}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse CSS to get font URL
        css_content = response.text
        font_urls = re.findall(r'url\((https://[^)]+\.woff2?)\)', css_content)
        
        if not font_urls:
            print(f"No font URLs found in CSS for {font_family}")
            return None
        
        # Download the first font file (usually woff2)
        font_url = font_urls[0]
        font_response = requests.get(font_url, timeout=15)
        font_response.raise_for_status()
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.woff2')
        temp_file.write(font_response.content)
        temp_file.close()
        
        print(f"Downloaded Google Font: {font_family} -> {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        print(f"Error downloading Google Font {font_family}: {e}")
        return None

def get_font_with_fallbacks(font_name: str, size: int, font_style: str = "regular") -> ImageFont.FreeTypeFont:
    """Get a font using your local fonts first, then Google Fonts as fallback"""
    font_candidates = []
    
    # 1. Try your local fonts FIRST (from Fonts/ folder)
    if font_name == "DS-Digital":
        # Prioritize DS-Digital fonts when specifically requested
        local_fonts = [
            str(Path("Fonts") / "ds_digital" / "DS-DIGIB.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGII.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGI.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGIT.TTF"),
        ]
    else:
        # Default local fonts for other font requests
        local_fonts = [
            str(Path("Fonts") / "capture_it" / "Capture it.ttf"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGIB.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGII.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGI.TTF"),
            str(Path("Fonts") / "ds_digital" / "DS-DIGIT.TTF"),
        ]
    font_candidates.extend(local_fonts)
    
    # 2. Try Google Fonts as fallback (only if local fonts fail)
    try:
        google_font_path = download_google_font(font_name, font_style)
        if google_font_path:
            font_candidates.append(google_font_path)
    except Exception as e:
        print(f"Google Fonts failed for {font_name}: {e}")
    
    # 3. Try system fonts
    system_fonts = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf", 
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
    ]
    font_candidates.extend(system_fonts)
    
    # Try each font candidate
    for font_path in font_candidates:
        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size)
                print(f"Successfully loaded font: {font_path}")
                return font
        except Exception as e:
            print(f"Failed to load font {font_path}: {e}")
            continue
    
    # Final fallback to default font
    print(f"All fonts failed, using default font for size {size}")
    try:
        return ImageFont.load_default().font_variant(size=size)
    except:
        return ImageFont.load_default()

def sanitize_username_for_poster(username: str) -> str:
    """Convert Discord display names to poster-friendly ASCII by stripping emojis and fancy Unicode.

    - Normalizes to NFKD and drops non-ASCII codepoints
    - Collapses repeated whitespace and trims ends
    - Falls back to 'Player' if empty after sanitization
    """
    try:
        import unicodedata
        # Normalize and strip accents/fancy letters
        normalized = unicodedata.normalize('NFKD', str(username))
        ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
        # Remove remaining characters that might be control or non-printable
        ascii_only = re.sub(r"[^\x20-\x7E]", "", ascii_only)
        # Collapse whitespace
        ascii_only = re.sub(r"\s+", " ", ascii_only).strip()
        return ascii_only if ascii_only else "Player"
    except Exception:
        return str(username) if username else "Player"

def get_random_template():
    """Get a random template image from the Templates folder"""
    template_path = "Templates"
    if os.path.exists(template_path):
        # Get all image files
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif']
        image_files = []
        for ext in image_extensions:
            image_files.extend(glob.glob(os.path.join(template_path, ext)))
            image_files.extend(glob.glob(os.path.join(template_path, ext.upper())))
        
        if image_files:
            return random.choice(image_files)
    return None

def create_event_poster(template_path: str, round_label: str, team1_captain: str, team2_captain: str, utc_time: str, date_str: str = None, server_name: str = "The Devil's Spot") -> str:
    """Create event poster with text overlays using Google Fonts and improved error handling"""
    print(f"Creating poster with template: {template_path}")
    
    try:
        # Validate template path
        if not os.path.exists(template_path):
            print(f"Template file not found: {template_path}")
            return None
            
        # Open the template image
        with Image.open(template_path) as img:
            print(f"Opened template image: {img.size}, mode: {img.mode}")
            
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize image to be smaller (max 800x600 to avoid Discord size limits)
            max_width, max_height = 800, 600
            width, height = img.size
            
            # Calculate new dimensions while maintaining aspect ratio
            if width > max_width or height > max_height:
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"Resized image to: {new_width}x{new_height}")
            
            # Create a copy to work with
            poster = img.copy()
            draw = ImageDraw.Draw(poster)
            
            # Get final image dimensions
            width, height = poster.size
            
            # Load fonts using the new system with Google Fonts integration
            print("Loading fonts...")
            
            # Define font sizes based on image height (reduced for better fit)
            title_size = int(height * 0.10)
            round_size = int(height * 0.14)
            vs_size = int(height * 0.09)
            time_size = int(height * 0.07)
            tiny_size = int(height * 0.05)
            
            # Load fonts with Google Fonts fallback
            try:
                # Use Square One font for server name, DS-Digital for round, date, and time
                font_title = get_font_with_fallbacks("Square One", title_size, "bold")  # Server name
                font_round = get_font_with_fallbacks("DS-Digital", round_size, "bold")  # Round text
                # Use a unique bundled font for player names so styling is consistent regardless of Discord nickname styling
                font_vs = get_font_with_fallbacks("Capture it", vs_size, "bold")       # Unique display font from Fonts/capture_it
                font_time = get_font_with_fallbacks("DS-Digital", time_size, "bold")  # Date and time
                font_tiny = get_font_with_fallbacks("Roboto", tiny_size)              # Small text
                
                print("Fonts loaded successfully")
                
            except Exception as font_error:
                print(f"Font loading error: {font_error}")
                # Ultimate fallback to default fonts
                font_title = ImageFont.load_default()
                font_round = ImageFont.load_default()
                font_vs = ImageFont.load_default()
                font_time = ImageFont.load_default()
                font_tiny = ImageFont.load_default()
            
            # Define colors for clean visibility
            text_color = (255, 255, 255)  # Bright white
            outline_color = (0, 0, 0)     # Pure black
            yellow_color = (255, 255, 0)  # Bright yellow for important text
            
            # Helper function to draw text with outline
            def draw_text_with_outline(text, x, y, font, text_color=text_color, use_yellow=False):
                x, y = int(x), int(y)
                final_text_color = yellow_color if use_yellow else text_color
                
                # Draw thick black outline for visibility
                outline_width = 4
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            try:
                                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
                            except Exception as e:
                                print(f"Error drawing outline: {e}")
                
                # Draw main text on top
                try:
                    draw.text((x, y), text, font=font, fill=final_text_color)
                except Exception as e:
                    print(f"Error drawing main text: {e}")
            
            # Add server name text (top center)
            try:
                server_text = server_name
                server_bbox = draw.textbbox((0, 0), server_text, font=font_title)
                server_width = server_bbox[2] - server_bbox[0]
                server_x = (width - server_width) // 2
                server_y = int(height * 0.08)
                draw_text_with_outline(server_text, server_x, server_y, font_title)
                print(f"Added server name: {server_text}")
            except Exception as e:
                print(f"Error adding server name: {e}")
            
            # Add Round text (center) - use yellow for emphasis
            try:
                round_text = f"ROUND {round_label}"
                round_bbox = draw.textbbox((0, 0), round_text, font=font_round)
                round_width = round_bbox[2] - round_bbox[0]
                round_x = (width - round_width) // 2
                round_y = int(height * 0.35)
                draw_text_with_outline(round_text, round_x, round_y, font_round, use_yellow=True)
                print(f"Added round text: {round_text}")
            except Exception as e:
                print(f"Error adding round text: {e}")
            
            # Add Captain vs Captain text (center)
            try:
                left_name_text = sanitize_username_for_poster(team1_captain)
                vs_core = " VS "
                right_name_text = sanitize_username_for_poster(team2_captain)

                # Measure text components to center the whole line
                left_box = draw.textbbox((0, 0), left_name_text, font=font_vs)
                vs_box = draw.textbbox((0, 0), vs_core, font=font_vs)
                right_box = draw.textbbox((0, 0), right_name_text, font=font_vs)
                
                total_width = (left_box[2] - left_box[0]) + (vs_box[2] - vs_box[0]) + (right_box[2] - right_box[0])
                current_x = (width - total_width) // 2
                vs_y = int(height * 0.55)

                # Draw left name
                draw_text_with_outline(left_name_text, current_x, vs_y, font_vs)
                current_x += (left_box[2] - left_box[0])
                
                # Draw VS
                draw_text_with_outline(vs_core, current_x, vs_y, font_vs, use_yellow=False)
                current_x += (vs_box[2] - vs_box[0])
                
                # Draw right name
                draw_text_with_outline(right_name_text, current_x, vs_y, font_vs)
                
                print(f"Added VS text: {left_name_text} VS {right_name_text}")
            except Exception as e:
                print(f"Error adding VS text: {e}")
            
            # Add date (if provided)
            if date_str:
                try:
                    date_text = f"DATE:  {date_str}"
                    date_bbox = draw.textbbox((0, 0), date_text, font=font_time)
                    date_width = date_bbox[2] - date_bbox[0]
                    date_x = (width - date_width) // 2
                    date_y = int(height * 0.72)
                    draw_text_with_outline(date_text, date_x, date_y, font_time)
                    print(f"Added date: {date_text}")
                except Exception as e:
                    print(f"Error adding date: {e}")
            
            # Add UTC time
            try:
                time_text = f"TIME:  {utc_time}"
                time_bbox = draw.textbbox((0, 0), time_text, font=font_time)
                time_width = time_bbox[2] - time_bbox[0]
                time_x = (width - time_width) // 2
                time_y = int(height * 0.82) if date_str else int(height * 0.75)
                draw_text_with_outline(time_text, time_x, time_y, font_time)
                print(f"Added time: {time_text}")
            except Exception as e:
                print(f"Error adding time: {e}")
            
            # Save the modified image
            output_path = f"temp_poster_{int(datetime.datetime.now().timestamp())}.png"
            poster.save(output_path, "PNG")
            print(f"Poster saved successfully: {output_path}")
            return output_path
            
    except Exception as e:
        print(f"Critical error creating poster: {e}")
        import traceback
        traceback.print_exc()
        return None

def calculate_time_difference(event_datetime: datetime.datetime, user_timezone: str = None) -> dict:
    """Calculate time difference and format for different timezones"""
    current_time = datetime.datetime.now()
    time_diff = event_datetime - current_time
    minutes_remaining = int(time_diff.total_seconds() / 60)
    
    # Format UTC time exactly as requested
    utc_time_str = event_datetime.strftime("%H:%M utc, %d/%m")
    
    # Try to detect user's local timezone
    local_timezone = None
    if user_timezone:
        try:
            local_timezone = pytz.timezone(user_timezone)
        except:
            pass
    
    # If no user timezone provided, try to detect from system
    if not local_timezone:
        try:
            # Try to get system timezone
            import time
            local_timezone = pytz.timezone(time.tzname[time.daylight])
        except:
            # Fallback to IST if detection fails
            local_timezone = pytz.timezone('Asia/Kolkata')
    
    # Calculate user's local time
    local_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(local_timezone)
    local_time_formatted = local_time.strftime("%A, %d %B, %Y %H:%M")
    
    # Calculate other common timezones
    ist_tz = pytz.timezone('Asia/Kolkata')
    ist_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(ist_tz)
    ist_formatted = ist_time.strftime("%A, %d %B, %Y %H:%M")
    
    est_tz = pytz.timezone('America/New_York')
    est_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(est_tz)
    est_formatted = est_time.strftime("%A, %d %B, %Y %H:%M")
    
    gmt_tz = pytz.timezone('Europe/London')
    gmt_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(gmt_tz)
    gmt_formatted = gmt_time.strftime("%A, %d %B, %Y %H:%M")
    
    return {
        'minutes_remaining': minutes_remaining,
        'utc_time': utc_time_str,
        'utc_time_simple': event_datetime.strftime("%H:%M UTC"),
        'local_time': local_time_formatted,
        'ist_time': ist_formatted,
        'est_time': est_formatted,
        'gmt_time': gmt_formatted
    }

def has_event_create_permission(interaction):
    """Check if user has permission to create events (Head Organizer, Head Helper or Helper Team)"""
    head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
    head_helper_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_helper"])
    helper_team_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["helper_team"])
    return head_organizer_role is not None or head_helper_role is not None or helper_team_role is not None

def has_event_result_permission(interaction):
    """Check if user has permission to post event results (Head Organizer, Head Helper, Helper Team, or Judge)"""
    head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
    head_helper_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_helper"])
    helper_team_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["helper_team"])
    judge_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["judge"])
    return head_organizer_role is not None or head_helper_role is not None or helper_team_role is not None or judge_role is not None

@bot.event
async def on_message(message):
    """Handle auto-response commands for ticket management"""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Only process messages that start with ? or $ and are in specific channels
    if not (message.content.startswith('?') or message.content.startswith('$')):
        return
    
    # Check if the command should be restricted to specific channels
    # For now, allow in all channels, but you can add restrictions here
    # Example: if message.channel.id not in [CHANNEL_IDS["take_schedule"], ...]:
    #     return
    
    # Extract command from message
    command = message.content.lower().strip()
    
    # Handle ticket status commands (?sh, ?dq, ?dd, ?ho, $close) - modify channel name prefix
    if command in ['?sh', '?dq', '?dd', '?ho', '$close']:
        # Check permissions for ticket management commands
        is_owner = message.author.id == BOT_OWNER_ID
        is_admin = message.author.guild_permissions.administrator if hasattr(message.author, 'guild_permissions') else False
        has_role = False
        
        if hasattr(message.author, 'roles'):
            head_org = discord.utils.get(message.author.roles, id=ROLE_IDS.get("head_organizer"))
            head_helper = discord.utils.get(message.author.roles, id=ROLE_IDS.get("head_helper"))
            helper_team = discord.utils.get(message.author.roles, id=ROLE_IDS.get("helper_team"))
            judge = discord.utils.get(message.author.roles, id=ROLE_IDS.get("judge"))
            has_role = bool(head_org or head_helper or helper_team or judge)
            
        if not (is_owner or is_admin or has_role):
            # No permission, quietly delete message and return
            try:
                await message.delete()
            except:
                pass
            return
            
        if command == '$close':
            try:
                closed_category_id = CHANNEL_IDS.get("closed_tickets_category", 1492915418556268605)
                closed_category = message.guild.get_channel(closed_category_id)
                if closed_category:
                    await message.channel.edit(
                        category=closed_category,
                        sync_permissions=True,
                        reason=f"Ticket closed by {message.author.name}"
                    )
                    await message.channel.send("🔒 Ticket closed and moved to the closed category.")
                else:
                    await message.channel.send("❌ Closed ticket category not found.")
                
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"Error closing ticket: {e}")
            return

        try:
            # Get the current channel
            channel = message.channel
            
            # Determine the new prefix based on command
            if command == '?sh':
                new_prefix = "🟢"
            elif command == '?dq':
                new_prefix = "🔴"
            elif command == '?dd':
                new_prefix = "✅"
            elif command == '?ho':
                new_prefix = "🟡"
            
            # Get current channel name
            current_name = channel.name
            
            # Remove existing status prefixes if they exist
            clean_name = current_name
            status_prefixes = ["🟢", "🔴", "✅", "🟡"]
            for prefix in status_prefixes:
                if clean_name.startswith(prefix):
                    clean_name = clean_name[len(prefix):].lstrip("-").lstrip()
                    break
            
            # Create new channel name with the status prefix
            new_name = f"{new_prefix}-{clean_name}"
            
            # Update channel name
            await channel.edit(name=new_name)
            
            # Delete the original command message after successful execution
            try:
                await message.delete()
            except discord.Forbidden:
                pass  # Ignore if we can't delete the message
            except Exception:
                pass  # Ignore any other deletion errors
            
        except discord.Forbidden:
            response = await message.channel.send("❌ I don't have permission to edit this channel's name.")
            try:
                await message.delete()
            except:
                pass
        except discord.HTTPException as e:
            response = await message.channel.send(f"❌ Error updating channel name: {e}")
            try:
                await message.delete()
            except:
                pass
        except Exception as e:
            response = await message.channel.send(f"❌ Unexpected error: {e}")
            try:
                await message.delete()
            except:
                pass
        
    elif command == '?b':
        # Challonge URL response
        response = await message.channel.send("https://challonge.com/Pandora_12")
        # Delete the original command message
        try:
            await message.delete()
        except discord.Forbidden:
            pass  # Ignore if we can't delete the message
        except Exception:
            pass  # Ignore any other deletion errors
    
    # Process other bot commands (important for command processing)
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    # Load scheduled events from file
    load_scheduled_events()
    
    # Load tournament rules from file
    load_rules()
    
    # Load staff stats from file
    load_staff_stats()
    
    # Reschedule cleanups for any events already marked finished_on if needed (optional)
    try:
        for ev_id, data in list(scheduled_events.items()):
            # If previously scheduled cleanup exists, skip (it won't persist); we don't know result time here
            # Optionally: clean up events older than 7 days to avoid clutter
            try:
                dt = data.get('datetime')
                if isinstance(dt, datetime.datetime):
                    age_days = (datetime.datetime.now() - dt).days
                    if age_days >= 7:
                        # Hard cleanup very old events
                        if ev_id in reminder_tasks:
                            try:
                                reminder_tasks[ev_id].cancel()
                                del reminder_tasks[ev_id]
                            except Exception:
                                pass
                        del scheduled_events[ev_id]
            except Exception:
                pass
        save_scheduled_events()
    except Exception as e:
        print(f"Startup cleanup sweep error: {e}")
    
    # Sync commands with timeout handling
    try:
        print("🔄 Syncing slash commands...")
        import asyncio
        synced = await asyncio.wait_for(tree.sync(), timeout=30.0)
        print(f"✅ Synced {len(synced)} command(s)")
    except asyncio.TimeoutError:
        print("⚠️ Command sync timed out, but bot will continue running")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")
        print("⚠️ Bot will continue running without command sync")
    
    print("🎯 Bot is ready to receive commands!")

@tree.command(name="help", description="Show available commands based on your permissions")
async def help_command(interaction: discord.Interaction):
    """Enhanced help command with role-based filtering — Ghost Fleet GR branded"""
    try:
        # Bot owner always gets owner level
        permission_level = get_user_permission_level(interaction.user.roles, interaction.user.id)
        
        bot_icon = interaction.client.user.display_avatar.url if interaction.client.user.display_avatar else None
        user_icon = interaction.user.display_avatar.url if interaction.user.display_avatar else None
        
        embed = build_help_embed(permission_level, interaction.user.display_name, bot_icon_url=bot_icon, user_icon_url=user_icon)
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    except Exception as e:
        print(f"Error in help command: {e}")
        await interaction.response.send_message("❌ An error occurred while generating help.", ephemeral=True)

@tree.command(name="staff-leaderboard", description="Display the staff activity leaderboard")
async def staff_leaderboard(interaction: discord.Interaction):
    """Rich visual staff leaderboard — Ghost Fleet GR"""
    try:
        if not staff_stats:
            embed = discord.Embed(
                title="📊 Staff Leaderboard — Ghost Fleet GR",
                description="No staff activity recorded yet. Stats will appear once matches are judged/recorded.",
                color=discord.Color(BRAND_COLOR),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text=f"{ORGANIZATION_NAME} • Staff Tracking")
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        # Sort by total (desc)
        sorted_staff = sorted(
            staff_stats.items(),
            key=lambda item: item[1].get('total_count', 0),
            reverse=True
        )
        top_staff = sorted_staff[:15]

        # Medal emojis for top 3
        rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}

        embed = discord.Embed(
            title="🏆 Staff Activity Leaderboard",
            description=(
                f"**{ORGANIZATION_NAME}**\n"
                "═══════════════════════════\n"
                f"Tracking the top **{len(top_staff)}** most active staff this tournament season."
            ),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )

        # Build a clean visual list (two compact columns)
        left_col  = ""
        right_col = ""

        for i, (user_id, stats) in enumerate(top_staff, 1):
            medal   = rank_emojis.get(i, f"`#{i:>2}`")
            name    = (stats.get('name') or 'Unknown')[:16]
            j_cnt   = stats.get('judge_count', 0)
            r_cnt   = stats.get('recorder_count', 0)
            total   = stats.get('total_count', 0)
            line = f"{medal} **{name}**\n⚖️ {j_cnt}  🎥 {r_cnt}  ✅ {total}\n"
            if i % 2 == 1:
                left_col += line
            else:
                right_col += line

        if left_col:
            embed.add_field(name="👥 Staff (odd)",  value=left_col,  inline=True)
        if right_col:
            embed.add_field(name="👥 Staff (even)", value=right_col, inline=True)

        # Summary stats
        total_matches = sum(s.get('total_count', 0) for _, s in top_staff)
        total_judged  = sum(s.get('judge_count', 0) for _, s in top_staff)
        total_rec     = sum(s.get('recorder_count', 0) for _, s in top_staff)
        embed.add_field(
            name="📈 Tournament Totals",
            value=(
                f"⚖️ **Total Judged:** {total_judged}\n"
                f"🎥 **Total Recorded:** {total_rec}\n"
                f"📊 **Combined Actions:** {total_matches}"
            ),
            inline=False
        )

        embed.set_footer(text=f"{ORGANIZATION_NAME} • Staff Leaderboard • ⚖️ Judge  🎥 Recorder  ✅ Total")

        # Show reset button only to organiser / bot owner
        is_owner = interaction.user.id == BOT_OWNER_ID
        head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
        view = JudgeLeaderboardView(show_reset=bool(head_organizer_role or is_owner))

        await interaction.response.send_message(embed=embed, view=view)

    except Exception as e:
        print(f"Error in staff-leaderboard command: {e}")
        await interaction.response.send_message("❌ An error occurred while generating the leaderboard.", ephemeral=True)

@tree.command(name="info", description="Display bot information and statistics")
async def info_command(interaction: discord.Interaction):
    """Display bot information and server statistics"""
    try:
        # Calculate statistics
        total_members = sum(g.member_count for g in bot.guilds)
        total_channels = sum(len(g.channels) for g in bot.guilds)
        
        # Create embed
        embed = discord.Embed(
            title=f"ℹ️ {ORGANIZATION_NAME} Bot Information",
            description="Tournament management bot for Modern Warships",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Bot Information
        embed.add_field(
            name="🤖 Bot Details",
            value=f"**Name:** {bot.user.name}\n"
                  f"**ID:** {bot.user.id}\n"
                  f"**Latency:** {round(bot.latency * 1000)}ms",
            inline=True
        )
        
        # Bot Statistics
        embed.add_field(
            name="📊 Bot Statistics",
            value=f"**Servers:** {len(bot.guilds)}\n"
                  f"**Users:** {total_members:,}\n"
                  f"**Channels:** {total_channels:,}",
            inline=True
        )
        
        # Server Information (if in a guild)
        if interaction.guild:
            embed.add_field(
                name="🏠 Current Server",
                value=f"**Name:** {interaction.guild.name}\n"
                      f"**Members:** {interaction.guild.member_count:,}\n"
                      f"**Created:** {interaction.guild.created_at.strftime('%d/%m/%Y')}",
                inline=True
            )
        
        # Commands Information
        total_commands = len(bot.tree.get_commands())
        embed.add_field(
            name="⚙️ Commands",
            value=f"**Total Commands:** {total_commands}\n"
                  f"**Categories:** Tournament, Event Management, Utility, System",
            inline=False
        )
        
        # Organization Info
        embed.add_field(
            name="🏆 Organization",
            value=f"{ORGANIZATION_NAME}\n"
                  f"Modern Warships Tournament System",
            inline=False
        )
        
        # Set thumbnail to bot avatar
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in info command: {e}")


    
@tree.command(name="team_balance", description="Balance two teams based on player levels")
@app_commands.describe(levels="Comma-separated player levels (e.g. 48,50,51,35,51,50,50,37,51,52)")
async def team_balance(interaction: discord.Interaction, levels: str):
    try:
        level_list = [int(x.strip()) for x in levels.split(",") if x.strip()]
        n = len(level_list)
        if n % 2 != 0:
            await interaction.response.send_message("❌ Number of players must be even (e.g., 8 or 10).", ephemeral=True)
            return

        team_size = n // 2
        min_diff = float('inf')
        best_team_a = []
        for combo in combinations(level_list, team_size):
            team_a = list(combo)
            team_b = list(level_list)
            for lvl in team_a:
                team_b.remove(lvl)
            diff = abs(sum(team_a) - sum(team_b))
            if diff < min_diff:
                min_diff = diff
                best_team_a = team_a
        team_b = list(level_list)
        for lvl in best_team_a:
            team_b.remove(lvl)
        sum_a = sum(best_team_a)
        sum_b = sum(team_b)
        diff = abs(sum_a - sum_b)
        await interaction.response.send_message(
            f"**Team A:** {best_team_a} | Total Level: {sum_a}\n"
            f"**Team B:** {team_b} | Total Level: {sum_b}\n"
            f"**Level Difference:** {diff}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="event", description="Event management commands")
@app_commands.describe(
    action="Select the event action to perform"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="result", value="result")
    ]
)
async def event(interaction: discord.Interaction, action: app_commands.Choice[str]):
    """Base event command - this will be handled by subcommands"""
    await interaction.response.send_message(f"Please use `/event {action.value}` with the appropriate parameters.", ephemeral=True)

@tree.command(name="event-create", description="Creates an event (Head Organizer/Head Helper/Helper Team only)")
@app_commands.describe(
    team_1_captain="Captain of team 1",
    team_2_captain="Captain of team 2", 
    hour="Hour of the event (0-23)",
    minute="Minute of the event (0-59)",
    date="Date of the event",
    month="Month of the event",
    round="Round label",
    tournament="Tournament name (e.g. King of the Seas, Summer Cup, etc.)",
    group="Group assignment (A-J) or Winner/Loser"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Qualifier"),
        app_commands.Choice(name="Semi Final", value="Semi Final"),
        app_commands.Choice(name="3rd Place", value="3rd Place"),
        app_commands.Choice(name="Final", value="Final"),
    ],
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ]
)
async def event_create(
    interaction: discord.Interaction,
    team_1_captain: discord.Member,
    team_2_captain: discord.Member,
    hour: int,
    minute: int,
    date: int,
    month: int,
    round: app_commands.Choice[str],
    tournament: str,
    group: app_commands.Choice[str] = None
):
    """Creates an event with the specified parameters"""
    
    # Defer the response to give us more time for image processing
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions
    if not has_event_create_permission(interaction):
        await interaction.followup.send("❌ You need **Head Organizer**, **Head Helper** or **Helper Team** role to create events.", ephemeral=True)
        return
    
    # Validate input parameters
    if not (0 <= hour <= 23):
        await interaction.followup.send("❌ Hour must be between 0 and 23", ephemeral=True)
        return
    
    if not (1 <= date <= 31):
        await interaction.followup.send("❌ Date must be between 1 and 31", ephemeral=True)
        return

    if not (1 <= month <= 12):
        await interaction.followup.send("❌ Month must be between 1 and 12", ephemeral=True)
        return
            
    if not (0 <= minute <= 59):
        await interaction.followup.send("❌ Minute must be between 0 and 59", ephemeral=True)
        return

    # Generate unique event ID
    event_id = f"event_{int(datetime.datetime.now().timestamp())}"
    
    # Create event datetime
    current_year = datetime.datetime.now().year
    event_datetime = datetime.datetime(current_year, month, date, hour, minute)
    
    # Calculate time differences and format times
    time_info = calculate_time_difference(event_datetime)
    
    # Resolve round label from choice
    round_label = round.value if isinstance(round, app_commands.Choice) else str(round)
    
    # Resolve group label from choice
    group_label = group.value if group and isinstance(group, app_commands.Choice) else None
    
    # Store event data for reminders
    scheduled_events[event_id] = {
        'title': f"Round {round_label} Match",
        'datetime': event_datetime,
        'time_str': time_info['utc_time'],
        'date_str': f"{date:02d}/{month:02d}",
        'round': round_label,
        'group': group_label,
        'minutes_left': time_info['minutes_remaining'],
        'tournament': tournament,
        'judge': None,
        'channel_id': interaction.channel.id,
        'team1_captain': team_1_captain,
        'team2_captain': team_2_captain
    }
    
    print(f"📝 Event {event_id} created internally for {team_1_captain.name} vs {team_2_captain.name}")
    
    # Save events to file
    save_scheduled_events()
    print(f"💾 Event {event_id} saved to file")
    
    # Get random template image and create poster (exact same as Sample Bot)
    template_image = get_random_template()
    poster_image = None
    
    if template_image:
        try:
            # Create poster with text overlays (exact same as Sample Bot)
            poster_image = create_event_poster(
                template_image, 
                round_label, 
                team_1_captain.name, 
                team_2_captain.name, 
                time_info['utc_time_simple'],
                f"{date:02d}/{month:02d}/{current_year}"
            )
            if poster_image:
                # Keep poster path for later cleanup/deletion
                scheduled_events[event_id]['poster_path'] = poster_image
                save_scheduled_events()
        except Exception as e:
            print(f"Error creating poster: {e}")
            poster_image = None
    else:
        print("No template images found in Templates folder")
    
    # Create event embed with new format
    embed = discord.Embed(
        title="Schedule",
        description=f"🗓️ {team_1_captain.name} VS {team_2_captain.name}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    # Tournament and Time Information
    # Create Discord timestamp for automatic timezone conversion
    timestamp = int(event_datetime.timestamp())
    # Build event details text
    event_details = f"**Tournament:** {tournament}\n"
    event_details += f"**UTC Time:** {time_info['utc_time']}\n"
    event_details += f"**Local Time:** <t:{timestamp}:F> (<t:{timestamp}:R>)\n"
    event_details += f"**Round:** {round_label}\n"
    
    # Add group if specified
    if group_label:
        event_details += f"**Group:** {group_label}\n"
    
    event_details += f"**Channel:** {interaction.channel.mention}"
    
    embed.add_field(
        name="📋 Event Details", 
        value=event_details,
        inline=False
    )
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Captains Section
    captains_text = f"**Captains**\n"
    captains_text += f"▪ Team1 Captain: {team_1_captain.mention} @{team_1_captain.name}\n"
    captains_text += f"▪ Team2 Captain: {team_2_captain.mention} @{team_2_captain.name}"
    embed.add_field(name="👑 Team Captains", value=captains_text, inline=False)
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    embed.add_field(name="👤 Created By", value=interaction.user.mention, inline=False)
    
    # Add poster image if available
    if poster_image:
        try:
            with open(poster_image, 'rb') as f:
                file = discord.File(f, filename="event_poster.png")
                embed.set_image(url="attachment://event_poster.png")
        except Exception as e:
            print(f"Error loading poster image: {e}")
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    # Create Take Schedule button
    take_schedule_view = TakeScheduleButton(event_id, team_1_captain, team_2_captain, interaction.channel)
    
    # Send confirmation to user
    await interaction.followup.send("✅ Event created and posted to both channels! Reminder will ping captains 10 minutes before start.", ephemeral=True)
    
    # Post in Take-Schedule channel (with button)
    try:
        schedule_channel = interaction.guild.get_channel(CHANNEL_IDS["take_schedule"])
        if schedule_channel:
            judge_ping = f"<@&{ROLE_IDS['judge']}>"
            if poster_image:
                with open(poster_image, 'rb') as f:
                    file = discord.File(f, filename="event_poster.png")
                    schedule_message = await schedule_channel.send(content=judge_ping, embed=embed, file=file, view=take_schedule_view)
            else:
                schedule_message = await schedule_channel.send(content=judge_ping, embed=embed, view=take_schedule_view)
            
            # Store the message ID for later deletion
            scheduled_events[event_id]['schedule_message_id'] = schedule_message.id
            scheduled_events[event_id]['schedule_channel_id'] = schedule_channel.id
        else:
            await interaction.followup.send("⚠️ Could not find Take-Schedule channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in Take-Schedule channel: {e}", ephemeral=True)
    
    # Post in the channel where command was used (without button)
    try:
        if poster_image:
            with open(poster_image, 'rb') as f:
                file = discord.File(f, filename="event_poster.png")
                await interaction.channel.send(embed=embed, file=file)
        else:
            await interaction.channel.send(embed=embed)

        # Schedule the 10-minute reminder
        await schedule_ten_minute_reminder(event_id, team_1_captain, team_2_captain, None, interaction.channel, event_datetime)
        
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in current channel: {e}", ephemeral=True)

@tree.command(name="event-result", description="Add event results (Head Organizer/Judge only)")
@app_commands.describe(
    winner="Winner of the event",
    winner_score="Winner's score",
    loser="Loser of the event", 
    loser_score="Loser's score",
    tournament="Tournament name (e.g., The Zumwalt S2)",
    round="Round name (e.g., Semi-Final, Final, Quarter-Final)",
    group="Group assignment (A-J) - optional",
    remarks="Remarks about the match (e.g., ggwp, close match)",
    recorder="Staff member who recorded the match (optional)",
    ss_1="Screenshot 1 (upload)",
    ss_2="Screenshot 2 (upload)",
    ss_3="Screenshot 3 (upload)",
    ss_4="Screenshot 4 (upload)",
    ss_5="Screenshot 5 (upload)",
    ss_6="Screenshot 6 (upload)",
    ss_7="Screenshot 7 (upload)",
    ss_8="Screenshot 8 (upload)",
    ss_9="Screenshot 9 (upload)",
    ss_10="Screenshot 10 (upload)",
    ss_11="Screenshot 11 (upload)"
)
@app_commands.choices(
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ]
)
async def event_result(
    interaction: discord.Interaction,
    winner: discord.Member,
    winner_score: int,
    loser: discord.Member,
    loser_score: int,
    tournament: str,
    round: str,
    group: app_commands.Choice[str] = None,
    remarks: str = "ggwp",
    recorder: discord.Member = None,
    ss_1: discord.Attachment = None,
    ss_2: discord.Attachment = None,
    ss_3: discord.Attachment = None,
    ss_4: discord.Attachment = None,
    ss_5: discord.Attachment = None,
    ss_6: discord.Attachment = None,
    ss_7: discord.Attachment = None,
    ss_8: discord.Attachment = None,
    ss_9: discord.Attachment = None,
    ss_10: discord.Attachment = None,
    ss_11: discord.Attachment = None
):
    """Adds results for an event"""
    
    # Defer the response immediately to avoid timeout issues
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions
    if not has_event_result_permission(interaction):
        await interaction.followup.send("❌ You need **Head Organizer** or **Judge** role to post event results.", ephemeral=True)
        return

    # Validate scores
    if winner_score < 0 or loser_score < 0:
        await interaction.followup.send("❌ Scores cannot be negative", ephemeral=True)
        return
            
    # Resolve group label from choice
    group_label = group.value if group and isinstance(group, app_commands.Choice) else None
            
    # Create results embed matching the exact template format
    embed_description = f"🗓️ {winner.name} Vs {loser.name}\n"
    embed_description += f"**Tournament:** {tournament}\n"
    embed_description += f"**Round:** {round}"
    
    # Add group if specified
    if group_label:
        embed_description += f"\n**Group:** {group_label}"
    
    embed = discord.Embed(
        title="Results",
        description=embed_description,
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    # Captains Section
    captains_text = f"**Captains**\n"
    captains_text += f"▪ Team1 Captain: {winner.mention} `@{winner.name}`\n"
    captains_text += f"▪ Team2 Captain: {loser.mention} `@{loser.name}`"
    embed.add_field(name="", value=captains_text, inline=False)
    
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False) 
    
    # Results Section
    results_text = f"**Results**\n"
    results_text += f"🏆 {winner.name} ({winner_score}) Vs ({loser_score}) {loser.name} 💀"
    embed.add_field(name="", value=results_text, inline=False)
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Staff Section
    staff_text = f"👨‍⚖️ **Staffs**\n"
    staff_text += f"▪ Judge: {interaction.user.mention}"
    if recorder:
        staff_text += f"\n▪ Recorder: {recorder.mention}"
    embed.add_field(name="", value=staff_text, inline=False)
    
    # Update staff statistics
    update_staff_stats(interaction.user, "judge")
    if recorder:
        update_staff_stats(recorder, "recorder")
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Embed setup
    topic = interaction.channel.topic
    if topic and "MatchID:" in topic:
        match_id_match = re.search(r'MatchID:(\d+)', topic)
        p1_match = re.search(r'P1:(\d+)', topic)
        p2_match = re.search(r'P2:(\d+)', topic)
        t1_match = re.search(r'Team1:(.*?) \|', topic)
        t2_match = re.search(r'Team2:(.*)', topic)
        
        if match_id_match and p1_match and p2_match:
            m_id = match_id_match.group(1)
            p1_id = p1_match.group(1)
            p2_id = p2_match.group(1)
            
            t1_name = t1_match.group(1).strip() if t1_match else None
            t2_name = t2_match.group(1).strip() if t2_match else None
            
            # Note: Bracket updating has been decoupled to a standalone command

    # Remarks Section
    embed.add_field(name="📝 Remarks", value=remarks, inline=False)
    
    # Handle screenshots - collect them and send as files (no image embeds)
    screenshots = [ss_1, ss_2, ss_3, ss_4, ss_5, ss_6, ss_7, ss_8, ss_9, ss_10, ss_11]
    files_to_send = []
    screenshot_names = []
    
    for i, screenshot in enumerate(screenshots, 1):
        if screenshot:
            # Create a file object for each screenshot
            try:
                file_data = await screenshot.read()
                file_obj = discord.File(
                    fp=io.BytesIO(file_data),
                    filename=f"SS-{i}_{screenshot.filename}"
                )
                files_to_send.append(file_obj)
                screenshot_names.append(f"SS-{i}")
            except Exception as e:
                print(f"Error processing screenshot {i}: {e}")
    
    # Add screenshot section if any screenshots were provided
    if screenshot_names:
        screenshot_text = f"**Screenshots of Result ({len(screenshot_names)} images)**\n"
        screenshot_text += f"📷 {' • '.join(screenshot_names)}"
        embed.add_field(name="", value=screenshot_text, inline=False)
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    # Send confirmation to user
    await interaction.followup.send("✅ Event results posted to Results channel, current channel, and Staff Attendance logged!", ephemeral=True)
    
    # Post in Results channel with screenshots as attachments
    results_posted = False
    try:
        results_channel = interaction.guild.get_channel(CHANNEL_IDS["results"])
        if results_channel:
            if files_to_send:
                # Create copies of files for results channel (files can only be used once)
                results_files = []
                for file_obj in files_to_send:
                    file_obj.fp.seek(0)  # Reset file pointer
                    file_data = file_obj.fp.read()
                    results_files.append(discord.File(
                        fp=io.BytesIO(file_data),
                        filename=file_obj.filename
                    ))
                await results_channel.send(embed=embed, files=results_files)
            else:
                await results_channel.send(embed=embed)
            results_posted = True
        else:
            await interaction.followup.send("⚠️ Could not find Results channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in Results channel: {e}", ephemeral=True)
    
    # Post in current channel (where command was executed)
    try:
        current_channel = interaction.channel
        if current_channel and current_channel.id != CHANNEL_IDS["results"]:  # Don't duplicate if already in results channel
            if files_to_send:
                # Reset file pointers and create new file objects for current channel
                current_files = []
                for file_obj in files_to_send:
                    file_obj.fp.seek(0)  # Reset file pointer
                    file_data = file_obj.fp.read()
                    current_files.append(discord.File(
                        fp=io.BytesIO(file_data),
                        filename=file_obj.filename
                    ))
                await current_channel.send(embed=embed, files=current_files)
            else:
                await current_channel.send(embed=embed)
        elif current_channel and current_channel.id == CHANNEL_IDS["results"] and not results_posted:
            # If we're in results channel but posting failed above, try again
            if files_to_send:
                await current_channel.send(embed=embed, files=files_to_send)
            else:
                await current_channel.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in current channel: {e}", ephemeral=True)

    # Winner-only summary removed per request
    
    # Post staff attendance in Staff Attendance channel — Ghost Fleet GR styled
    try:
        staff_attendance_channel = interaction.guild.get_channel(CHANNEL_IDS["staff_attendance"])
        if staff_attendance_channel:
            att_embed = discord.Embed(
                title="📋 Staff Attendance Log",
                description=(
                    f"🏅 **{winner.name}** vs **{loser.name}**\n"
                    f"**Tournament:** {tournament}\n"
                    f"**Round:** {round}"
                    + (f"\n**Group:** {group_label}" if group_label else "")
                ),
                color=discord.Color(BRAND_COLOR),
                timestamp=discord.utils.utcnow()
            )
            att_embed.add_field(
                name="🏆 Result",
                value=f"**Winner:** {winner.mention} `({winner_score})`\n**Loser:** {loser.mention} `({loser_score})`",
                inline=False
            )
            staff_val = f"⚖️ **Judge:** {interaction.user.mention}"
            if recorder:
                staff_val += f"\n🎥 **Recorder:** {recorder.mention}"
            att_embed.add_field(name="👥 Staff on Duty", value=staff_val, inline=False)
            att_embed.set_footer(text=f"{ORGANIZATION_NAME} • Attendance")
            await staff_attendance_channel.send(embed=att_embed)
        else:
            print("⚠️ Could not find Staff Attendance channel.")
    except Exception as e:
        print(f"⚠️ Could not post in Staff Attendance channel: {e}")

    # Schedule auto-cleanup of matching events in this channel after 36 hours
    try:
        current_channel_id = interaction.channel.id if interaction.channel else None
        matching_event_ids = []
        for ev_id, data in scheduled_events.items():
            if data.get('channel_id') == current_channel_id:
                # Optional: further match by captains to be safer
                try:
                    t1 = getattr(data.get('team1_captain'), 'id', None)
                    t2 = getattr(data.get('team2_captain'), 'id', None)
                    if winner.id in (t1, t2) and loser.id in (t1, t2):
                        matching_event_ids.append(ev_id)
                        
                        # Update the event with result data
                        scheduled_events[ev_id]['result_added'] = True
                        scheduled_events[ev_id]['result_winner'] = winner
                        scheduled_events[ev_id]['result_loser'] = loser
                        scheduled_events[ev_id]['result_winner_score'] = winner_score
                        scheduled_events[ev_id]['result_loser_score'] = loser_score
                        scheduled_events[ev_id]['result_judge'] = interaction.user
                        scheduled_events[ev_id]['result_group'] = group_label
                        scheduled_events[ev_id]['result_remarks'] = remarks
                        
                        print(f"Updated event {ev_id} with result data")
                except Exception as e:
                    print(f"Error updating event {ev_id}: {e}")
                    matching_event_ids.append(ev_id)

        # Save updated events
        if matching_event_ids:
            save_scheduled_events()

        scheduled_any = False
        for ev_id in matching_event_ids:
            # Update the original schedule message title with checkmark
            try:
                event_data = scheduled_events.get(ev_id)
                if event_data:
                    schedule_channel_id = event_data.get('schedule_channel_id')
                    schedule_message_id = event_data.get('schedule_message_id')
                    
                    if schedule_channel_id and schedule_message_id:
                        schedule_channel = interaction.guild.get_channel(schedule_channel_id)
                        if schedule_channel:
                            try:
                                schedule_message = await schedule_channel.fetch_message(schedule_message_id)
                                if schedule_message.embeds:
                                    embed = schedule_message.embeds[0]
                                    # Update title with checkmark
                                    if update_embed_title_with_checkmark(embed):
                                        try:
                                            await schedule_message.edit(embed=embed)
                                            print(f"Updated schedule title with checkmark for event {ev_id}")
                                        except discord.Forbidden:
                                            print(f"Bot doesn't have permission to edit message in channel {schedule_channel.name}")
                                        except Exception as edit_error:
                                            print(f"Error editing schedule message for event {ev_id}: {edit_error}")
                            except discord.NotFound:
                                print(f"Schedule message not found for event {ev_id}")
                            except Exception as e:
                                print(f"Error updating schedule title for event {ev_id}: {e}")
            except Exception as e:
                print(f"Error processing title update for event {ev_id}: {e}")
            
            await schedule_event_cleanup(ev_id, delay_hours=36)
            scheduled_any = True
        
        # Also update any schedule messages in the current channel
        try:
            current_channel = interaction.channel
            if current_channel:
                # Look for recent messages in current channel that might be schedule messages
                async for message in current_channel.history(limit=50):
                    if message.embeds and message.author == bot.user:
                        embed = message.embeds[0]
                        # Check if this looks like a schedule message with green circle
                        if embed.title and embed.title.startswith("🟢"):
                            # Check if this matches our winner/loser
                            description = embed.description or ""
                            if (winner.name in description and loser.name in description) or \
                               (winner.display_name in description and loser.display_name in description) or \
                               (winner.mention in description and loser.mention in description):
                                if update_embed_title_with_checkmark(embed):
                                    try:
                                        await message.edit(embed=embed)
                                        print(f"Updated current channel schedule title with checkmark")
                                    except discord.Forbidden:
                                        print(f"Bot doesn't have permission to edit message in current channel")
                                    except Exception as edit_error:
                                        print(f"Error editing current channel message: {edit_error}")
                                break
        except Exception as e:
            print(f"Error updating current channel schedule title: {e}")

        if scheduled_any:
            await interaction.followup.send("🧹 Auto-cleanup scheduled: Related event(s) will be removed after 36 hours.", ephemeral=True)
    except Exception as e:
        print(f"Error scheduling auto-cleanup after results: {e}")

@tree.command(name="time", description="Get a random match time from fixed 30-min slots (12:00-17:00 UTC)")
async def time(interaction: discord.Interaction):
    """Pick a random time from 30-minute slots between 12:00 and 17:00 UTC and show all slots."""
    
    import random
    
    # Build fixed 30-minute slots from 12:00 to 17:00 (inclusive), excluding 17:30
    slots = [
        f"{hour:02d}:{minute:02d} UTC"
        for hour in range(12, 18)
        for minute in (0, 30)
        if not (hour == 17 and minute == 30)
    ]
    
    chosen_time = random.choice(slots)
    
    embed = discord.Embed(
        title="⏰ Match Time (30‑min slots)",
        description=f"**Your random match time:** {chosen_time}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
                    )
                                       
    embed.add_field(
        name="🕒 Range",
        value="From 12:00 to 17:00 UTC (every 30 minutes)",
        inline=False
    )
                    
    embed.set_footer(text=f"Match Time Generator • {ORGANIZATION_NAME}")
    
    await interaction.response.send_message(embed=embed)

## Removed test-poster command per request


@tree.command(name="unassigned_events", description="List events without a judge assigned (Judges/Organizers)")
async def unassigned_events(interaction: discord.Interaction):
    """Show all scheduled events that do not currently have a judge assigned."""
    try:
        # Allow Head Organizer, Head Helper, Helper Team, and Judges to view
        head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"]) if interaction.user else None
        head_helper_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_helper"]) if interaction.user else None
        helper_team_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["helper_team"]) if interaction.user else None
        judge_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["judge"]) if interaction.user else None

        if not (head_organizer_role or head_helper_role or helper_team_role or judge_role):
            await interaction.response.send_message("❌ You need Organizer or Judge role to view unassigned events.", ephemeral=True)
            return

        # Build list of unassigned events
        unassigned = []
        for event_id, data in scheduled_events.items():
            if not data.get('judge'):
                unassigned.append((event_id, data))

        # If none, inform
        if not unassigned:
            await interaction.response.send_message("✅ All events currently have a judge assigned.", ephemeral=True)
            return

        # Sort by datetime if present
        try:
            unassigned.sort(key=lambda x: x[1].get('datetime') or datetime.datetime.max)
        except Exception:
            pass

        # Create embed summary
        embed = discord.Embed(
            title="📝 Unassigned Events",
            description="Events without a judge. Use the message link to take the schedule.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )

        # Add up to 25 entries (Discord practical limit for a single embed field block)
        lines = []
        for idx, (ev_id, data) in enumerate(unassigned[:25], start=1):
            round_label = data.get('round', 'Round')
            date_str = data.get('date_str', 'N/A')
            time_str = data.get('time_str', 'N/A')
            ch_id = data.get('schedule_channel_id') or data.get('channel_id')
            msg_id = data.get('schedule_message_id')
            team1 = data.get('team1_captain')
            team2 = data.get('team2_captain')
            team1_name = getattr(team1, 'name', 'Unknown') if team1 else 'Unknown'
            team2_name = getattr(team2, 'name', 'Unknown') if team2 else 'Unknown'

            link = None
            try:
                if interaction.guild and ch_id and msg_id:
                    link = f"https://discord.com/channels/{interaction.guild.id}/{ch_id}/{msg_id}"
            except Exception:
                link = None

            if link:
                line = f"{idx}. {team1_name} vs {team2_name} • {round_label} • {time_str} • {date_str}\n↪ {link}"
            else:
                line = f"{idx}. {team1_name} vs {team2_name} • {round_label} • {time_str} • {date_str}"
            lines.append(line)

        embed.add_field(
            name=f"Available ({len(unassigned)})",
            value="\n\n".join(lines),
            inline=False
        )

        embed.set_footer(text="Use the link to open the original schedule and press Take Schedule.")

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"Error in unassigned_events: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred while fetching unassigned events.", ephemeral=True)
        except Exception:
            pass

@tree.command(name="event-delete", description="Delete a scheduled event (Head Organizer/Head Helper/Helper Team only)")
async def event_delete(interaction: discord.Interaction):
    # Check permissions - only Head Organizer, Head Helper or Helper Team can delete events
    head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
    head_helper_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_helper"])
    helper_team_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["helper_team"])
    
    if not (head_organizer_role or head_helper_role or helper_team_role):
        await interaction.response.send_message("❌ You need **Head Organizer**, **Head Helper** or **Helper Team** role to delete events.", ephemeral=True)
        return
    
    try:
        # Check if there are any scheduled events
        if not scheduled_events:
            await interaction.response.send_message(f"❌ No scheduled events found to delete.\n\n**Debug Info:**\n• Scheduled events count: {len(scheduled_events)}\n• Events in memory: {list(scheduled_events.keys()) if scheduled_events else 'None'}", ephemeral=True)
            return
        
        # Create dropdown with event names
        class EventDeleteView(View):
            def __init__(self):
                super().__init__(timeout=60)
                
            @discord.ui.select(
                placeholder="Select an event to delete...",
                options=[
                    discord.SelectOption(
                        label=f"{event_data.get('team1_captain').name if event_data.get('team1_captain') else 'Unknown'} VS {event_data.get('team2_captain').name if event_data.get('team2_captain') else 'Unknown'}",
                        description=f"{event_data.get('round', 'Unknown Round')} - {event_data.get('date_str', 'No date')} at {event_data.get('time_str', 'No time')}",
                        value=event_id
                    )
                    for event_id, event_data in list(scheduled_events.items())[:25]  # Discord limit of 25 options
                ]
            )
            async def select_event(self, select_interaction: discord.Interaction, select: discord.ui.Select):
                selected_event_id = select.values[0]
                
                # Get event details for confirmation
                event_data = scheduled_events[selected_event_id]
                
                # Cancel any scheduled reminders
                if selected_event_id in reminder_tasks:
                    reminder_tasks[selected_event_id].cancel()
                    del reminder_tasks[selected_event_id]
                
                # Remove judge assignment if exists
                if 'judge' in event_data and event_data['judge']:
                    judge_id = event_data['judge'].id
                    remove_judge_assignment(judge_id, selected_event_id)
                
                # Delete the original schedule message if it exists
                deleted_message = False
                if 'schedule_message_id' in event_data and 'schedule_channel_id' in event_data:
                    try:
                        schedule_channel = select_interaction.guild.get_channel(event_data['schedule_channel_id'])
                        if schedule_channel:
                            schedule_message = await schedule_channel.fetch_message(event_data['schedule_message_id'])
                            await schedule_message.delete()
                            deleted_message = True
                    except discord.NotFound:
                        pass  # Message already deleted
                    except Exception as e:
                        print(f"Error deleting schedule message: {e}")
                
                # Clean up any temporary poster files
                if 'poster_path' in event_data:
                    try:
                        import os
                        if os.path.exists(event_data['poster_path']):
                            os.remove(event_data['poster_path'])
                    except Exception as e:
                        print(f"Error deleting poster file: {e}")
                
                # Remove from scheduled events
                del scheduled_events[selected_event_id]
                
                # Save events to file
                save_scheduled_events()
                
                # Create confirmation embed
                embed = discord.Embed(
                    title="🗑️ Event Deleted",
                    description=f"Event has been successfully deleted.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                
                embed.add_field(
                    name="📋 Deleted Event Details",
                    value=f"**Title:** {event_data.get('title', 'N/A')}\n**Round:** {event_data.get('round', 'N/A')}\n**Time:** {event_data.get('time_str', 'N/A')}\n**Date:** {event_data.get('date_str', 'N/A')}",
                    inline=False
                )
                
                # Build actions completed list
                actions_completed = [
                    "• Event removed from schedule",
                    "• Reminder cancelled",
                    "• Judge assignment cleared"
                ]
                
                if deleted_message:
                    actions_completed.append("• Original schedule message deleted")
                
                if 'poster_path' in event_data:
                    actions_completed.append("• Temporary poster file cleaned up")
                
                embed.add_field(
                    name="✅ Actions Completed",
                    value="\n".join(actions_completed),
                    inline=False
                )
                
                embed.set_footer(text=f"Event Management • {ORGANIZATION_NAME}")
                
                await select_interaction.response.edit_message(embed=embed, view=None)
        
        # Create initial embed
        embed = discord.Embed(
            title="🗑️ Delete Event",
            description="Select an event from the dropdown below to delete it.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Available Events",
            value=f"Found {len(scheduled_events)} scheduled event(s)",
            inline=False
        )
        
        embed.set_footer(text=f"Event Management • {ORGANIZATION_NAME}")
        
        view = EventDeleteView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(name='staff-update', description="Update a staff member's match count in the leaderboard")
@app_commands.describe(staff_member='The staff member to update', role='Role to update (judge or recorder)', action='Add, Subtract, or Set the count', amount='The number of matches to add, subtract, or set to')
@app_commands.choices(role=[
    app_commands.Choice(name='Judge', value='judge'),
    app_commands.Choice(name='Recorder', value='recorder')
], action=[
    app_commands.Choice(name='Add (+)', value='add'),
    app_commands.Choice(name='Subtract (-)', value='subtract'),
    app_commands.Choice(name='Set (=)', value='set')
])
async def staff_update(interaction: discord.Interaction, staff_member: discord.Member, role: app_commands.Choice[str], action: app_commands.Choice[str], amount: int):
    """Update staff statistics for a specific user"""
    org_role_keys = ['head_organizer', 'deputy_server_head', 'Tournament_organizer', 'Tournament_supervision']
    org_role_ids = [ROLE_IDS.get(k) for k in org_role_keys if ROLE_IDS.get(k)]
    has_permission = any((r.id in org_role_ids for r in interaction.user.roles)) if hasattr(interaction.user, 'roles') else False
    if not has_permission:
        await interaction.response.send_message('❌ You need **Head Organizer** role to update staff statistics.', ephemeral=True)
        return

    if amount < 0 and action.value != 'subtract':
        await interaction.response.send_message('❌ Amount cannot be negative.', ephemeral=True)
        return

    global staff_stats
    uid = str(staff_member.id)
    if uid not in staff_stats:
        staff_stats[uid] = {'name': staff_member.display_name, 'judge_count': 0, 'recorder_count': 0, 'last_activity': None}
    else:
        staff_stats[uid]['name'] = staff_member.display_name

    role_key = f'{role.value}_count'
    current_count = staff_stats[uid].get(role_key, 0)
    
    if action.value == 'add':
        new_count = current_count + amount
    elif action.value == 'subtract':
        new_count = max(0, current_count - amount)
    else:
        new_count = max(0, amount)

    staff_stats[uid][role_key] = new_count
    staff_stats[uid]['last_activity'] = datetime.datetime.utcnow().isoformat()
    save_staff_stats()

    await interaction.response.send_message(f"✅ Successfully updated **{staff_member.display_name}**'s {role.name} count from {current_count} to **{new_count}**.", ephemeral=False)


CURRENT_TOURNAMENT_NAME = ""



@tree.command(name='tournament-setup', description='Wipe all old data and set up for a new tournament (Bot Owner Only)')
@app_commands.describe(
    bracket_link='The official bracket link for the new tournament',
    bracket_api_key='The Bracket API Key for the tournament',
    google_sheet_link='The Google Sheet Link for the tournament',
    tournament_name='Name of the new tournament'
)
async def tournament_setup(
    interaction: discord.Interaction, 
    bracket_link: str,
    bracket_api_key: str,
    google_sheet_link: str,
    tournament_name: str
):
    user_roles = [r.id for r in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
    is_owner = interaction.user.id == BOT_OWNER_ID
    is_organizer = ROLE_IDS.get("head_organizer") in user_roles
    
    try:
        is_owner_client = await interaction.client.is_owner(interaction.user)
    except:
        is_owner_client = False
        
    if not (is_owner or is_owner_client or is_organizer):
        await interaction.response.send_message('❌ This command is restricted to the Bot Owner or Head Organizer.', ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)
    status = []

    global scheduled_events, staff_stats, tournament_rules, reminder_tasks, cleanup_tasks, judge_assignments
    global BRACKET_LINK, BRACKET_API_KEY, GOOGLE_SHEET_LINK, CURRENT_TOURNAMENT_NAME
    
    # Update configurations
    BRACKET_LINK = bracket_link
    BRACKET_API_KEY = bracket_api_key
    GOOGLE_SHEET_LINK = google_sheet_link
    CURRENT_TOURNAMENT_NAME = tournament_name
    save_config()
    status.append('✅ **Configuration:** Bracket, Sheet, and Tournament Name updated successfully.')

    # Cancel active event background tasks
    for task in reminder_tasks.values():
        if not task.done():
            task.cancel()
    reminder_tasks.clear()
    
    for task in cleanup_tasks.values():
        if not task.done():
            task.cancel()
    cleanup_tasks.clear()
    
    # Clear active assignments
    judge_assignments.clear()
    
    scheduled_events.clear()
    staff_stats.clear()
    tournament_rules.clear()

    if bracket_link:
        tournament_rules['bracket_link'] = bracket_link

    try:
        import os
        if os.path.exists('scheduled_events.json'):
            os.remove('scheduled_events.json')
        if os.path.exists('staff_stats.json'):
            os.remove('staff_stats.json')
        if os.path.exists('tournament_rules.json'):
            os.remove('tournament_rules.json')
        db_msg = "> 🔸 Local Matches Wiped\n> 🔸 Staff Leaderboards Cleared\n> 🔸 Active Alarms Destroyed"
    except Exception as e:
        db_msg = f"> ❌ Failed to wipe local storage: {e}"

    save_scheduled_events()
    save_staff_stats()
    save_rules()

    embed = discord.Embed(
        title=f"🛑 TOURNAMENT HARD-RESET: {CURRENT_TOURNAMENT_NAME}",
        description=(
            "**All Core Systems Synchronized & Wiped Successfully.**\n"
            "Your database is now completely clean and ready for a fresh competitive season.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.brand_red()
    )
    
    embed.add_field(name="⚙️ __Configurations__", value="> 🔹 Tournament Name Updated\n> 🔹 Google Sheet API Linked\n> 🔹 Challonge Bracket Linked", inline=False)
    embed.add_field(name="🗑️ __Data Purge__", value=db_msg, inline=False)
    
    embed.add_field(
        name='📝 __Next Steps Required__',
        value=(
            f"**1.** Execute `/tournament-start` when you are ready to generate match tickets.\n"
            f"**2.** Use the `/rules` command to instantly write and broadcast the new season's competitive guidelines directly into your Discord's rules category."
        ),
        inline=False
    )
    
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
        
    embed.set_footer(text=f'Initialization complete • {ORGANIZATION_NAME}')
    
    await interaction.followup.send(embed=embed)


@tree.command(name="exchange", description="Exchange a Judge or Recorder for an event")
@app_commands.describe(
    role="Role to exchange",
    old_user="The old staff member removing access from",
    new_user="The new staff member granting access to"
)
@app_commands.choices(role=[
    app_commands.Choice(name="Judge", value="judge"),
    app_commands.Choice(name="Recorder", value="recorder")
])
async def exchange(interaction: discord.Interaction, role: app_commands.Choice[str], old_user: discord.Member, new_user: discord.Member):
    """Exchanges a staff member for events in the current channel, swapping their permissions."""
    if not (has_event_create_permission(interaction) or has_event_result_permission(interaction)):
        await interaction.response.send_message("❌ You need **Head Organizer**, **Head Helper**, **Helper Team** or **Judge** role to exchange staff.", ephemeral=True)
        return

    current_channel_id = interaction.channel.id
    target_event_ids = []
    
    for ev_id, data in scheduled_events.items():
        if data.get('channel_id') == current_channel_id:
            if role.value == 'judge' and getattr(data.get('judge'), 'id', None) == old_user.id:
                target_event_ids.append(ev_id)
            elif role.value == 'recorder' and getattr(data.get('recorder'), 'id', None) == old_user.id:
                target_event_ids.append(ev_id)

    if not target_event_ids:
        await interaction.response.send_message(f"⚠️ No events in this channel are assigned to {old_user.mention} as a {role.name}.", ephemeral=True)
        return

    updated_count = 0
    for ev_id in target_event_ids:
        data = scheduled_events.get(ev_id)
        if not data:
            continue
            
        try:
            await interaction.channel.set_permissions(old_user, overwrite=None)
            await interaction.channel.set_permissions(new_user, view_channel=True, send_messages=True, read_messages=True, embed_links=True, attach_files=True, read_message_history=True)
        except Exception as e:
            print(f"Error setting permissions in exchange: {e}")

        if role.value == 'judge':
            data['judge'] = new_user
            try:
                remove_judge_assignment(old_user.id, ev_id)
            except Exception:
                pass
            add_judge_assignment(new_user.id, ev_id)
        else:
            data['recorder'] = new_user

        save_scheduled_events()
        
        team1 = data.get('team1_captain')
        team2 = data.get('team2_captain')
        current_judge = data.get('judge')
        
        pings = ""
        if team1:
            pings += f"{team1.mention} "
        if team2:
            pings += f"{team2.mention} "
        if current_judge:
            pings += f"{current_judge.mention} "
            
        notify_embed = discord.Embed(
            title="🔄 Staff Exchange Notification",
            description=f"Staff assignment for this match has been updated.\n\n**Role:** {role.name}\n**Old Staff:** {old_user.mention} `@{old_user.name}`\n**New Staff:** {new_user.mention} `@{new_user.name}`\n**Updated by:** {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        channel_mention = interaction.channel.mention
        notify_embed.add_field(
            name="📋 Event",
            value=f"{channel_mention} • Time: {data.get('time_str', '')} • {data.get('round', '')}",
            inline=False
        )
        notify_embed.set_footer(text=f"{ORGANIZATION_NAME} • Match Update")
        
        if pings:
            await interaction.channel.send(content=f"🔔 {pings}", embed=notify_embed)
        else:
            await interaction.channel.send(embed=notify_embed)
            
        updated_count += 1
        
    await interaction.response.send_message(f"✅ {new_user.mention} is now the **{role.name}** for {updated_count} event(s), replacing {old_user.mention}.", ephemeral=True)


@tree.command(name="event-edit", description="Edit the event in this ticket channel (Head Organizer/Head Helper/Helper Team only)")
@app_commands.describe(
    team_1_captain="Captain of team 1 (optional)",
    team_2_captain="Captain of team 2 (optional)", 
    hour="Hour of the event (0-23) (optional)",
    minute="Minute of the event (0-59) (optional)",
    date="Date of the event (optional)",
    month="Month of the event (optional)",
    round="Round label (optional)",
    tournament="Tournament name (optional)",
    group="Group assignment (A-J) or Winner/Loser (optional)"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Qualifier"),
        app_commands.Choice(name="Semi Final", value="Semi Final"),
        app_commands.Choice(name="3rd Place", value="3rd Place"),
        app_commands.Choice(name="Final", value="Final"),
    ],
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ]
)
async def event_edit(
    interaction: discord.Interaction,
    team_1_captain: discord.Member = None,
    team_2_captain: discord.Member = None,
    hour: int = None,
    minute: int = None,
    date: int = None,
    month: int = None,
    round: app_commands.Choice[str] = None,
    tournament: str = None,
    group: app_commands.Choice[str] = None
):
    """Edit the event in this ticket channel"""
    
    # Defer the response to give us more time for processing
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions - Bot Owner, Head Organizer, Head Helper or Helper Team can edit events
    if interaction.user.id != BOT_OWNER_ID:
        if not has_event_create_permission(interaction):
            await interaction.followup.send("❌ You need **Bot Owner**, **Head Organizer**, **Head Helper** or **Helper Team** role to edit events.", ephemeral=True)
            return
    
    # Find event in current channel
    current_channel_id = interaction.channel.id
    event_to_edit = None
    event_id = None
    
    for ev_id, event_data in scheduled_events.items():
        if event_data.get('channel_id') == current_channel_id:
            event_to_edit = event_data
            event_id = ev_id
            break
    
    if not event_to_edit:
        await interaction.followup.send("❌ No event found in this ticket channel. Use `/event-create` to create an event first.", ephemeral=True)
        return
    
    # Check if at least one field is provided
    if not any([team_1_captain, team_2_captain, hour is not None, minute is not None, date is not None, month is not None, round, tournament, group]):
        await interaction.followup.send("❌ Please provide at least one field to update.", ephemeral=True)
        return
    
    # Validate input parameters only if provided
    if hour is not None and not (0 <= hour <= 23):
        await interaction.followup.send("❌ Hour must be between 0 and 23", ephemeral=True)
        return
    
    if date is not None and not (1 <= date <= 31):
        await interaction.followup.send("❌ Date must be between 1 and 31", ephemeral=True)
        return

    if month is not None and not (1 <= month <= 12):
        await interaction.followup.send("❌ Month must be between 1 and 12", ephemeral=True)
        return
            
    if minute is not None and not (0 <= minute <= 59):
        await interaction.followup.send("❌ Minute must be between 0 and 59", ephemeral=True)
        return

    try:
        # Get current event data
        current_datetime = event_to_edit.get('datetime', datetime.datetime.now())
        current_hour = hour if hour is not None else current_datetime.hour
        current_minute = minute if minute is not None else current_datetime.minute
        current_date = date if date is not None else current_datetime.day
        current_month = month if month is not None else current_datetime.month
        
        # Create new datetime
        current_year = datetime.datetime.now().year
        new_datetime = datetime.datetime(current_year, current_month, current_date, current_hour, current_minute)
        
        # Calculate time differences
        time_info = calculate_time_difference(new_datetime)
        
        # Update only provided fields
        if team_1_captain:
            event_to_edit['team1_captain'] = team_1_captain
        if team_2_captain:
            event_to_edit['team2_captain'] = team_2_captain
        if hour is not None or minute is not None or date is not None or month is not None:
            event_to_edit['datetime'] = new_datetime
            event_to_edit['time_str'] = time_info['utc_time']
            event_to_edit['date_str'] = f"{current_date:02d}/{current_month:02d}"
            event_to_edit['minutes_left'] = time_info['minutes_remaining']
        if round:
            round_label = round.value if isinstance(round, app_commands.Choice) else str(round)
            event_to_edit['round'] = round_label
        if tournament:
            event_to_edit['tournament'] = tournament
        if group:
            event_to_edit['group'] = group.value
        
        # Save updated events
        save_scheduled_events()
        
        # Schedule the 10-minute reminder with updated event data
        try:
            await schedule_ten_minute_reminder(event_id, team1_captain, team2_captain, event_to_edit.get('judge'), interaction.channel, new_datetime)
        except Exception as e:
            print(f"Error scheduling reminder for updated event {event_id}: {e}")
        
        # Get updated event details for public posting
        team1_captain = event_to_edit.get('team1_captain')
        team2_captain = event_to_edit.get('team2_captain')
        round_info = event_to_edit.get('round', 'Unknown')
        tournament_info = event_to_edit.get('tournament', 'Unknown')
        time_info_display = event_to_edit.get('time_str', 'Unknown')
        date_info_display = event_to_edit.get('date_str', 'Unknown')
        group_info = event_to_edit.get('group', '')
        
        # Create public embed for updated event (similar to event-create)
        embed = discord.Embed(
            title="📝 Event Updated",
            description=f"**Event has been updated by {interaction.user.mention}**",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        # Event Details Section
        embed.add_field(
            name="📋 Updated Event Details", 
            value=f"**Team 1 Captain:** {team1_captain.mention if team1_captain else 'Unknown'} `@{team1_captain.name if team1_captain else 'Unknown'}`\n"
                  f"**Team 2 Captain:** {team2_captain.mention if team2_captain else 'Unknown'} `@{team2_captain.name if team2_captain else 'Unknown'}`\n"
                  f"**UTC Time:** {time_info_display}\n"
                  f"**Local Time:** <t:{int(new_datetime.timestamp())}:F> (<t:{int(new_datetime.timestamp())}:R>)\n"
                  f"**Round:** {round_info}\n"
                  f"**Tournament:** {tournament_info}\n"
                  f"**Channel:** {interaction.channel.mention}",
            inline=False
        )
        
        if group_info:
            embed.add_field(
                name="🏆 Group Assignment",
                value=f"**Group:** {group_info}",
                inline=False
            )
        
        # Add spacing
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # Captains Section
        captains_text = f"**Captains**\n"
        captains_text += f"▪ Team1 Captain: {team1_captain.mention if team1_captain else 'Unknown'} `@{team1_captain.name if team1_captain else 'Unknown'}`\n"
        captains_text += f"▪ Team2 Captain: {team2_captain.mention if team2_captain else 'Unknown'} `@{team2_captain.name if team2_captain else 'Unknown'}`"
        embed.add_field(name="", value=captains_text, inline=False)
        
        embed.set_footer(text=f"Event Updated • {ORGANIZATION_NAME}")
        
        # Post the updated event publicly in the channel
        await interaction.channel.send(embed=embed)
        
        # Send private confirmation to the user who edited
        await interaction.followup.send("✅ Event updated successfully and posted in the channel!", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error updating event: {str(e)}", ephemeral=True)


@tree.command(name="general_tie_breaker", description="To break a tie between two teams using the highest total score")
@app_commands.describe(
    tm1_name="Name of the first team. By default, it is Alpha",
    tm1_pl1_score="Score of the first player of the first team",
    tm1_pl2_score="Score of the second player of the first team", 
    tm1_pl3_score="Score of the third player of the first team",
    tm1_pl4_score="Score of the fourth player of the first team",
    tm1_pl5_score="Score of the fifth player of the first team",
    tm2_name="Name of the second team. By default, it is Bravo",
    tm2_pl1_score="Score of the first player of the second team",
    tm2_pl2_score="Score of the second player of the second team",
    tm2_pl3_score="Score of the third player of the second team",
    tm2_pl4_score="Score of the fourth player of the second team",
    tm2_pl5_score="Score of the fifth player of the second team"
)
async def general_tie_breaker(
    interaction: discord.Interaction,
    tm1_pl1_score: int,
    tm1_pl2_score: int,
    tm1_pl3_score: int,
    tm1_pl4_score: int,
    tm1_pl5_score: int,
    tm2_pl1_score: int,
    tm2_pl2_score: int,
    tm2_pl3_score: int,
    tm2_pl4_score: int,
    tm2_pl5_score: int,
    tm1_name: str = "Alpha",
    tm2_name: str = "Bravo"
):
    """Break a tie between two teams using the highest total score"""
    
    # Check permissions - only organizers and helpers can use this command
    if not has_event_create_permission(interaction):
        await interaction.response.send_message("❌ You need **Organizers** or **Helpers Tournament** role to use tie breaker.", ephemeral=True)
        return
    
    # Calculate team totals
    tm1_total = tm1_pl1_score + tm1_pl2_score + tm1_pl3_score + tm1_pl4_score + tm1_pl5_score
    tm2_total = tm2_pl1_score + tm2_pl2_score + tm2_pl3_score + tm2_pl4_score + tm2_pl5_score
    
    # Determine winner
    if tm1_total > tm2_total:
        winner = tm1_name
        winner_total = tm1_total
        loser = tm2_name
        loser_total = tm2_total
        color = discord.Color.green()
    elif tm2_total > tm1_total:
        winner = tm2_name
        winner_total = tm2_total
        loser = tm1_name
        loser_total = tm1_total
        color = discord.Color.green()
    else:
        # Still tied
        winner = "TIE"
        winner_total = tm1_total
        loser = ""
        loser_total = tm2_total
        color = discord.Color.orange()
    
    # Create result embed
    embed = discord.Embed(
        title="🏆 Tie Breaker Results",
        description="Results based on highest total team score",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Team 1 scores
    embed.add_field(
        name=f"🔵 {tm1_name} Team",
        value=f"Player 1: `{tm1_pl1_score}`\n"
              f"Player 2: `{tm1_pl2_score}`\n"
              f"Player 3: `{tm1_pl3_score}`\n"
              f"Player 4: `{tm1_pl4_score}`\n"
              f"Player 5: `{tm1_pl5_score}`\n"
              f"**Total: {tm1_total}**",
        inline=True
    )
    
    # Team 2 scores
    embed.add_field(
        name=f"🔴 {tm2_name} Team",
        value=f"Player 1: `{tm2_pl1_score}`\n"
              f"Player 2: `{tm2_pl2_score}`\n"
              f"Player 3: `{tm2_pl3_score}`\n"
              f"Player 4: `{tm2_pl4_score}`\n"
              f"Player 5: `{tm2_pl5_score}`\n"
              f"**Total: {tm2_total}**",
        inline=True
    )
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Result
    if winner == "TIE":
        embed.add_field(
            name="🤝 Final Result",
            value=f"**STILL TIED!**\n"
                  f"Both teams scored {tm1_total} points\n"
                  f"Additional tie-breaking method needed",
            inline=False
        )
    else:
        embed.add_field(
            name="🏆 Winner",
            value=f"**{winner}** wins the tie breaker!\n"
                  f"**{winner}**: {winner_total} points\n"
                  f"**{loser}**: {loser_total} points\n"
                  f"Difference: {abs(winner_total - loser_total)} points",
            inline=False
        )
    
    embed.set_footer(text=f"Tie Breaker • Calculated by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="add_captain", description="Add two captains to a tournament match and rename the channel")
@app_commands.describe(
    round="Round of the tournament (R1-R10, Q, SF, Final)",
    captain1="First captain/team for the match",
    captain2="Second captain/team for the match",
    bracket="Optional bracket identifier (e.g., A, B, Winner, Loser)"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Q"),
        app_commands.Choice(name="Semi Final", value="SF"),
        app_commands.Choice(name="3rd Place", value="3rd Place"),
        app_commands.Choice(name="Final", value="Final")
    ]
)
async def add_captain(interaction: discord.Interaction, round: str, captain1: discord.Member, captain2: discord.Member, bracket: str = None):
    """Add two captains to a tournament match and rename the channel with tournament rules."""
    try:
        # Check permissions - only Head Helper, Helper Team, Head Organizer, or Bot Owner can add captains
        head_helper_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_helper"])
        helper_team_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["helper_team"])
        head_organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["head_organizer"])
        
        # Check if user is bot owner
        is_bot_owner = interaction.user.id == BOT_OWNER_ID
        
        if not any([head_helper_role, helper_team_role, head_organizer_role, is_bot_owner]):
            await interaction.response.send_message("❌ You don't have permission to use this command. Only Head Helper, Helper Team, Head Organizer, or Bot Owner can add captains.", ephemeral=True)
            return
        
        # Validate round parameter
        valid_rounds = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "Q", "SF", "Final"]
        if round not in valid_rounds:
            await interaction.response.send_message("❌ Invalid round. Please select R1-R10, Q, SF, or Final.", ephemeral=True)
            return
        
        # Get current channel
        channel = interaction.channel
        
        # Create new channel name
        if bracket:
            new_name = f"{bracket}-{round.lower()}-{captain1.name.lower()}-vs-{captain2.name.lower()}"
        else:
            new_name = f"{round.lower()}-{captain1.name.lower()}-vs-{captain2.name.lower()}"
        
        # Remove special characters and spaces, replace with hyphens
        new_name = re.sub(r'[^a-zA-Z0-9\-]', '-', new_name)
        new_name = re.sub(r'-+', '-', new_name)  # Replace multiple hyphens with single hyphen
        new_name = new_name.strip('-')  # Remove leading/trailing hyphens
        
        # Ensure channel name is within Discord's limits (100 characters max)
        if len(new_name) > 100:
            new_name = new_name[:100]
        
        # Rename the channel
        try:
            await channel.edit(name=new_name)
            await interaction.response.send_message(f"✅ Channel renamed to `{new_name}`", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to rename this channel.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to rename channel: {e}", ephemeral=True)
            return
        
        # Add both captains to the channel
        try:
            # Add captain 1 to the channel
            await channel.set_permissions(captain1, 
                                         view_channel=True,
                                         send_messages=True)
            
            # Add captain 2 to the channel
            await channel.set_permissions(captain2, 
                                         view_channel=True,
                                         send_messages=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Channel renamed but couldn't add captains - missing permissions.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"⚠️ Channel renamed but error adding captains: {e}", ephemeral=True)
        
        # Send tournament rules message — Ghost Fleet GR branded
        rules_embed = discord.Embed(
            title="⚓ Ghost Fleet GR — Match Setup",
            description="Welcome to your match channel. Use this channel for all tournament discussions.",
            color=discord.Color(BRAND_COLOR)
        )
        rules_embed.add_field(
            name="📋 Tournament Information",
            value=(
                f"• 🏆 [Live Bracket]({LINK_BRACKET}) — View current standings\n"
                f"• ⏰ [Match Deadlines]({LINK_DEADLINE}) — Schedule & timings\n"
                f"• 📜 [Tournament Rules]({LINK_RULES}) — Read before playing"
            ),
            inline=False
        )
        rules_embed.add_field(
            name="👥 Match Participants",
            value=f"**Round:** {round}\n**Captain 1:** {captain1.mention}\n**Captain 2:** {captain2.mention}",
            inline=False
        )
        rules_embed.add_field(
            name="🆘 Need Help?",
            value=f"Ping <@&{ROLE_IDS['helper_team']}> and a staff member will assist you.",
            inline=False
        )
        rules_embed.add_field(
            name="🤝 Fair Play",
            value="We appreciate your cooperation. Good luck and have fun! ⚓",
            inline=False
        )
        rules_embed.set_footer(text=f"{ORGANIZATION_NAME} | Setup by {interaction.user.name} • {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}")
        try:
            logo_candidates = ["Ghost Fleet GR logo.png", "Vᴀʟᴏʀᴀɴᴛ Vᴀɴɢᴜᴀʀᴅ E-ꜱᴩᴏʀᴛꜱ logo.png", "logo.png"]
            logo_sent = False
            for logo_path in logo_candidates:
                try:
                    with open(logo_path, "rb") as logo_file:
                        logo_data = io.BytesIO(logo_file.read())
                        lf = discord.File(logo_data, filename="logo.png")
                        rules_embed.set_thumbnail(url="attachment://logo.png")
                        await channel.send(embed=rules_embed, file=lf)
                        logo_sent = True
                        break
                except FileNotFoundError:
                    continue
            if not logo_sent:
                await channel.send(embed=rules_embed)
        except Exception as e:
            print(f"Warning: Could not send logo: {e}")
            await channel.send(embed=rules_embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in add_captain command: {e}")


@tree.command(name='tournament-start', description='Start tournament matches and create tickets for open matches')
@app_commands.describe(
    tournament_name='Name of the tournament (optional override, uses saved name by default)'
)
async def tournament_start(interaction: discord.Interaction, tournament_name: Optional[str]=None):
    user_roles = [r.id for r in interaction.user.roles] if hasattr(interaction.user, 'roles') else []
    is_owner = interaction.user.id == BOT_OWNER_ID
    is_organizer = ROLE_IDS.get("head_organizer") in user_roles
    
    if not (is_owner or is_organizer):
        await interaction.response.send_message("❌ You need **Head Organizer** role to start a tournament.", ephemeral=True)
        return

    await interaction.response.defer()

    progress = discord.Embed(
        title="⚙️ Tournament Automation Progress",
        description="Synchronizing data across systems...",
        color=discord.Color.blue()
    )
    progress.add_field(name="Step 1: System Config", value="⏳ Checking database...", inline=False)
    progress.add_field(name="Step 2: Challonge API", value="⏳ Waiting...", inline=False)
    progress.add_field(name="Step 3: Google Sheets API", value="⏳ Waiting...", inline=False)
    progress.add_field(name="Step 4: Ticket Creation", value="⏳ Waiting...", inline=False)
    
    await interaction.edit_original_response(embed=progress)

    # ── Step 1: Config check ──────────────────────────────────────────
    missing = []
    if not BRACKET_LINK:   missing.append("Bracket Link")
    if not BRACKET_API_KEY: missing.append("Bracket API Key")
    if not GOOGLE_SHEET_LINK: missing.append("Google Sheet Link")
    if missing:
        progress.color = discord.Color.red()
        progress.set_field_at(0, name="Step 1: System Config", value=f"❌ **Failed!** Missing: `{'`, `'.join(missing)}`", inline=False)
        await interaction.edit_original_response(embed=progress)
        return

    progress.set_field_at(0, name="Step 1: System Config", value="✅ Verified successfully", inline=False)
    progress.set_field_at(1, name="Step 2: Challonge API", value="🔄 Fetching live bracket data...", inline=False)
    await interaction.edit_original_response(embed=progress)

    # ── Step 2: Challonge ─────────────────────────────────────────────
    matches, err = await fetch_challonge_open_matches(BRACKET_LINK, BRACKET_API_KEY)
    if err:
        progress.color = discord.Color.red()
        progress.set_field_at(1, name="Step 2: Challonge API", value=f"❌ **Error:** {err}", inline=False)
        await interaction.edit_original_response(embed=progress)
        return
    if not matches:
        progress.color = discord.Color.green()
        progress.set_field_at(1, name="Step 2: Challonge API", value="✅ No open matches right now. All caught up!", inline=False)
        progress.description = "Tournament is fully up to date."
        await interaction.edit_original_response(embed=progress)
        return

    progress.set_field_at(1, name="Step 2: Challonge API", value=f"✅ Found **{len(matches)}** open match(es)", inline=False)
    progress.set_field_at(2, name="Step 3: Google Sheets API", value="🔄 Downloading captain roster...", inline=False)
    await interaction.edit_original_response(embed=progress)

    # ── Step 3: Google Sheet ──────────────────────────────────────────
    captains_dict, is_1v1, err2 = await fetch_google_sheet_captains(GOOGLE_SHEET_LINK)
    if err2:
        progress.color = discord.Color.red()
        progress.set_field_at(2, name="Step 3: Google Sheets API", value=f"❌ **Error:** {err2}", inline=False)
        await interaction.edit_original_response(embed=progress)
        return

    progress.set_field_at(2, name="Step 3: Google Sheets API", value=f"✅ Loaded {len(captains_dict)} team records", inline=False)
    progress.set_field_at(3, name="Step 4: Ticket Creation", value="🔄 Creating Discord channels...", inline=False)
    await interaction.edit_original_response(embed=progress)

    # ── Step 4: Create channels ───────────────────────────────────────
    primary_category_id = CHANNEL_IDS.get("category_1", 1492915175836221532)
    backup_category_id = CHANNEL_IDS.get("category_2", 1492915301602430996)
    
    cat_primary = discord.utils.get(interaction.guild.categories, id=primary_category_id)
    cat_backup = discord.utils.get(interaction.guild.categories, id=backup_category_id)
    
    if not cat_primary and not cat_backup:
        await interaction.followup.send(f"❌ Neither Primary Category `{primary_category_id}` nor Backup Category `{backup_category_id}` were found. Check the IDs.")
        return

    created_channels = []
    skipped = []
    errors = []
    t_name = tournament_name or CURRENT_TOURNAMENT_NAME
    helper_team_role = discord.utils.get(interaction.guild.roles, id=ROLE_IDS["helper_team"])

    total_matches = len(matches)
    bar_init = '░' * 20
    progress.set_field_at(3, name="Step 4: Ticket Creation", value=f"🔄 Creating rooms...\n`[{bar_init}] 0% (0/{total_matches})`", inline=False)
    await interaction.edit_original_response(embed=progress)

    for i, match in enumerate(matches, 1):
        team1 = match['team1']
        team2 = match['team2']
        p1_id = match['player1_id']
        p2_id = match['player2_id']
        match_id = match['id']
        mod_round = match['round']

        # Lookup captain raw values from sheet
        c1_raw = captains_dict.get(team1, "") or captains_dict.get(team1.strip(), "")
        c2_raw = captains_dict.get(team2, "") or captains_dict.get(team2.strip(), "")

        # Extract Discord user ID from mention (<@id>, <@!id>) or plain number
        def extract_uid(raw: str):
            m = re.search(r'<@!?(\d+)>', raw)
            if m:
                return int(m.group(1))
            if raw.strip().isdigit():
                return int(raw.strip())
            return None

        captain1: discord.Member = None
        captain2: discord.Member = None

        uid1 = extract_uid(c1_raw)
        uid2 = extract_uid(c2_raw)

        if uid1:
            try:
                captain1 = await interaction.guild.fetch_member(uid1)
            except Exception as e:
                print(f"[tournament-start] Could not fetch member {uid1}: {e}")
        if uid2:
            try:
                captain2 = await interaction.guild.fetch_member(uid2)
            except Exception as e:
                print(f"[tournament-start] Could not fetch member {uid2}: {e}")

        # Build channel name
        if is_1v1:
            n1 = captain1.name.lower() if captain1 else re.sub(r'[^a-zA-Z0-9]', '', team1).lower()[:12]
            n2 = captain2.name.lower() if captain2 else re.sub(r'[^a-zA-Z0-9]', '', team2).lower()[:12]
            chan_name = f"r{mod_round}-{n1}-vs-{n2}"
        else:
            safe_t1 = re.sub(r'[^a-zA-Z0-9]', '', team1).lower()[:8]
            safe_t2 = re.sub(r'[^a-zA-Z0-9]', '', team2).lower()[:8]
            c1_sfx = captain1.name.lower()[:6] if captain1 else 'cap1'
            c2_sfx = captain2.name.lower()[:6] if captain2 else 'cap2'
            chan_name = f"r{mod_round}-{safe_t1}{c1_sfx}-vs-{safe_t2}{c2_sfx}"

        chan_name = re.sub(r'[^a-zA-Z0-9\-]', '-', chan_name)
        chan_name = re.sub(r'-+', '-', chan_name).strip('-')[:100]

        topic = f"MatchID:{match_id} | P1:{p1_id} | P2:{p2_id} | Team1:{team1} | Team2:{team2}"

        already_exists = False
        for c in filter(None, [cat_primary, cat_backup]):
            if discord.utils.get(c.channels, name=chan_name):
                already_exists = True
                break
                
        if already_exists:
            skipped.append(chan_name)
            continue

        target_category = cat_primary
        if cat_primary and len(cat_primary.channels) >= 49:
            target_category = cat_backup

        try:
            # Replicate robust Ticket Tool authorizations natively
            overwrites = {}
            if target_category and target_category.overwrites:
                overwrites = dict(target_category.overwrites)
            
            # 1. Hide from public
            if interaction.guild.default_role not in overwrites:
                overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            else:
                overwrites[interaction.guild.default_role].view_channel = False

            # 2. Allow bot & creator universally
            overwrites[interaction.guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_permissions=True)
            overwrites[interaction.user] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            # 3. Allow Staff
            for role_key in ["head_organizer", "head_helper", "helper_team"]:
                r_id = ROLE_IDS.get(role_key)
                if r_id:
                    staff_r = discord.utils.get(interaction.guild.roles, id=r_id)
                    if staff_r:
                        overwrites[staff_r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            # 4. Allow Captains
            if captain1:
                overwrites[captain1] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            if captain2:
                overwrites[captain2] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            new_ch = await interaction.guild.create_text_channel(
                name=chan_name,
                category=target_category,
                topic=topic,
                overwrites=overwrites
            )

            created_channels.append(new_ch.mention)

            # Build match setup embed — Ghost Fleet GR branded
            rules_embed = discord.Embed(
                title="⚓ Ghost Fleet GR — Match Setup",
                description="Welcome to your match channel. Use this channel for all tournament discussions.",
                color=discord.Color(BRAND_COLOR)
            )
            rules_embed.add_field(
                name="📋 Tournament Information",
                value=(
                    f"• 🏆 [Live Bracket]({LINK_BRACKET}) — View current standings\n"
                    f"• ⏰ [Match Deadlines]({LINK_DEADLINE}) — Schedule & timings\n"
                    f"• 📜 [Tournament Rules]({LINK_RULES}) — Read before playing"
                ),
                inline=False
            )

            if is_1v1:
                pval = (
                    f"**Round:** R{mod_round}\n"
                    f"**Captain 1:** {captain1.mention if captain1 else c1_raw or team1}\n"
                    f"**Captain 2:** {captain2.mention if captain2 else c2_raw or team2}"
                )
            else:
                pval = (
                    f"**Round:** R{mod_round}\n"
                    f"**Team 1:** {team1} — Captain: {captain1.mention if captain1 else c1_raw or 'Not Found'}\n"
                    f"**Team 2:** {team2} — Captain: {captain2.mention if captain2 else c2_raw or 'Not Found'}"
                )

            rules_embed.add_field(name="👥 Match Participants", value=pval, inline=False)
            rules_embed.add_field(
                name="🆘 Need Help?",
                value=f"Ping {helper_team_role.mention if helper_team_role else '@Helper Team'} and a staff member will assist you.",
                inline=False
            )
            rules_embed.add_field(
                name="🤝 Fair Play",
                value="We appreciate your cooperation. Good luck and have fun! ⚓",
                inline=False
            )
            rules_embed.set_footer(
                text=f"{ORGANIZATION_NAME} | {interaction.user.name} • {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"
            )

            ping_content = " ".join(filter(None, [
                captain1.mention if captain1 else (c1_raw or None),
                captain2.mention if captain2 else (c2_raw or None),
            ])) or f"{team1} vs {team2}"

            logo_candidates_ts = ["Ghost Fleet GR logo.png", "Vᴀʟᴏʀᴀɴᴛ Vᴀɴɢᴜᴀʀᴅ E-ꜱᴩᴏʀᴛꜱ logo.png", "logo.png"]
            sent_logo = False
            for lp in logo_candidates_ts:
                try:
                    with open(lp, "rb") as lf:
                        ld = io.BytesIO(lf.read())
                        lf2 = discord.File(ld, filename="logo.png")
                        rules_embed.set_thumbnail(url="attachment://logo.png")
                        await new_ch.send(content=ping_content, embed=rules_embed, file=lf2)
                        sent_logo = True
                        break
                except FileNotFoundError:
                    continue
                except Exception as logo_e:
                    print(f"[tournament-start] Logo error: {logo_e}")
                    break
            if not sent_logo:
                await new_ch.send(content=ping_content, embed=rules_embed)

        except Exception as ch_e:
            errors.append(f"`{chan_name}`: {ch_e}")
            print(f"[tournament-start] Channel creation error {chan_name}: {ch_e}")

        # Live Update Progress Bar every 2 iterations to avoid Discord API limits
        if i % 2 == 0 or i == total_matches:
            filled = int(20 * i / total_matches)
            bar = '▓' * filled + '░' * (20 - filled)
            pct = int((i / total_matches) * 100)
            progress.set_field_at(
                3, 
                name="Step 4: Ticket Creation", 
                value=f"🔄 Creating rooms...\n`[{bar}] {pct}% ({i}/{total_matches})`", 
                inline=False
            )
            try:
                await interaction.edit_original_response(embed=progress)
            except Exception:
                pass

    # ── Final summary ─────────────────────────────────────────────────
    progress.color = discord.Color.green()
    progress.description = "✅ Setup complete! All systems operational."
    
    val_lines = []
    if created_channels:
        val_lines.append(f"🎫 **Created {len(created_channels)} tickets**")
    if skipped:
        val_lines.append(f"⏭️ **Skipped {len(skipped)} existing tickets**")
    if errors:
        val_lines.append(f"⚠️ **{len(errors)} errors** (see logs)")
    
    if not val_lines:
        val_lines.append("No actions needed.")
        
    progress.set_field_at(3, name="Step 4: Ticket Creation", value="\n".join(val_lines), inline=False)
    await interaction.edit_original_response(embed=progress)




@tree.command(name="maps", description="Randomly select 3, 5, or 7 maps for gameplay")
@app_commands.describe(
    count="Number of maps to select (3, 5, or 7)"
)
async def maps(interaction: discord.Interaction, count: int):
    """Randomly selects 3, 5, or 7 maps from the available map pool"""
    
    import random
    
    # Predefined map list
    maps_list = [
        "New Storm (2024)",
        "Arid Frontier", 
        "Islands of Iceland",
        "Unexplored Rocks",
        "Arctic",
        "Lost City",
        "Polar Frontier",
        "Hidden Dragon",
        "Monstrous Maelstrom",
        "Two Samurai",
        "Stone Peaks",
        "Viking Bay",
        "Greenlands",
        "Old Storm"
    ]
    
    # Validate count
    if count not in [3, 5, 7]:
        await interaction.response.send_message("❌ Please select 3, 5, or 7 maps only.", ephemeral=True)
        return
    
    # Randomly select the specified number of maps
    selected_maps = random.sample(maps_list, count)
    
    embed = discord.Embed(
        title=f"🗺️ Random Map Selection {ORGANIZATION_NAME}",
        description=f"**Randomly selected {count} map(s):**",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    
    # Add selected maps as a field
    selected_maps_text = "\n".join([f"• {map_name}" for map_name in selected_maps])
    embed.add_field(
        name=f"🎯 Selected Maps ({count})",
        value=selected_maps_text,
        inline=False
    )
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="test_channels", description="Test if bot can access configured channels (Organizer only)")
async def test_channels(interaction: discord.Interaction):
    """Test channel access for debugging"""
    
    # Check permissions
    user_roles = [role.id for role in interaction.user.roles]
    is_owner = interaction.user.id == BOT_OWNER_ID
    is_organizer = ROLE_IDS["head_organizer"] in user_roles
    
    if not (is_owner or is_organizer):
        await interaction.response.send_message(
            "❌ You need to be **Bot Owner** or **Head Organizer** to use this command.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🔍 Channel Access Test",
        description="Testing bot access to configured channels...",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    # Test each channel
    for channel_name, channel_id in CHANNEL_IDS.items():
        channel = interaction.guild.get_channel(channel_id)
        
        if channel:
            # Check if bot can send messages
            perms = channel.permissions_for(interaction.guild.me)
            can_send = perms.send_messages
            can_embed = perms.embed_links
            can_attach = perms.attach_files
            can_mention = perms.mention_everyone
            
            status = "✅" if (can_send and can_embed) else "⚠️"
            details = f"Channel: {channel.mention}\n"
            details += f"• Send Messages: {'✅' if can_send else '❌'}\n"
            details += f"• Embed Links: {'✅' if can_embed else '❌'}\n"
            details += f"• Attach Files: {'✅' if can_attach else '❌'}\n"
            details += f"• Mention Everyone: {'✅' if can_mention else '❌'}"
            
            embed.add_field(
                name=f"{status} {channel_name.replace('_', ' ').title()}",
                value=details,
                inline=False
            )
        else:
            embed.add_field(
                name=f"❌ {channel_name.replace('_', ' ').title()}",
                value=f"Channel ID `{channel_id}` not found!\nThe channel may have been deleted or the ID is wrong.",
                inline=False
            )
    
    embed.set_footer(text=f"{ORGANIZATION_NAME}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="choose", description="Randomly choose from a list of options")
@app_commands.describe(
    options="List of options separated by commas"
)
async def choose(interaction: discord.Interaction, options: str):
    """Randomly selects one option from a comma-separated list"""
    
    import random
    
    # Handle comma-separated options (original functionality)
    option_list = [option.strip() for option in options.split(',') if option.strip()]
    
    # Validate input
    if len(option_list) < 2:
        await interaction.response.send_message("❌ Please provide at least 2 options separated by commas.", ephemeral=True)
        return
    
    if len(option_list) > 20:
        await interaction.response.send_message("❌ Too many options! Please provide 20 or fewer options.", ephemeral=True)
        return
    
    # Randomly select one option
    chosen_option = random.choice(option_list)
    
    # Create embed
    embed = discord.Embed(
        title="🎲 Random Choice",
        description=f"**Selected:** {chosen_option}",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    # Add all options as a field
    options_text = "\n".join([f"• {option}" for option in option_list])
    embed.add_field(
        name=f"📋 Available Options ({len(option_list)})",
        value=options_text,
        inline=False
    )
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    await interaction.response.send_message(embed=embed)

class RulesModal(discord.ui.Modal, title='Publish Tournament Rules'):
    title_text = discord.ui.TextInput(
        label='Rules Title',
        style=discord.TextStyle.short,
        placeholder='e.g., Official Tournament Rules',
        default='🏆 Official Tournament Rules',
        required=True,
        max_length=100
    )
    rules_text = discord.ui.TextInput(
        label='Enter Tournament Rules',
        style=discord.TextStyle.paragraph,
        placeholder='Type out the rules here. Formatting like **bold** and *italics* is allowed.',
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel_id = CHANNEL_IDS.get("rules", 1493371304860979434)
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(f"❌ Could not find the Rules channel (ID: {channel_id}). Please check the ID.", ephemeral=True)
            return

        embed = discord.Embed(
            title=self.title_text.value,
            description=self.rules_text.value,
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{ORGANIZATION_NAME} | Published by {interaction.user.name}")
        
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Rules have been successfully published in {channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ I don't have permission to send messages in {channel.mention}.", ephemeral=True)


@tree.command(name='rules', description='Write and publish new tournament rules to the guidelines channel')
async def publish_rules(interaction: discord.Interaction):
    # Organizers or judges only
    if not (has_event_create_permission(interaction) or has_event_result_permission(interaction)):
        await interaction.response.send_message("❌ You lack permission to publish rules.", ephemeral=True)
        return
        
    await interaction.response.send_modal(RulesModal())

@tree.command(name='find-tickets', description='Secret debug command to find where tickets live')
async def find_tickets(interaction: discord.Interaction):
    category_id = CHANNEL_IDS.get("category_1", 1492915175836221532)
    lines = []
    
    cat = discord.utils.get(interaction.guild.categories, id=category_id)
    if cat:
        lines.append(f"✅ **Target Category:** '{cat.name}' (ID: {category_id}) - contains {len(cat.channels)} channels.")
    else:
        lines.append(f"❌ **Category ID {category_id} not found in this server!**")
        
    found = []
    for ch in interaction.guild.channels:
        if ch.name.startswith('r') and '-vs-' in ch.name:
            parent_name = ch.category.name if ch.category else "NO CATEGORY (At top of server!)"
            found.append(f"{ch.mention} -> `{parent_name}`")
            
    lines.append(f"\n🔍 **Found {len(found)} tournament ticket channels total:**")
    lines.extend(found[:20])
    if len(found) > 20: lines.append(f"...and {len(found)-20} more.")
    
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

async def auto_create_open_tickets(guild: discord.Guild, user: discord.Member):
    # Automatic background ticket creation for open matches
    if not (BRACKET_LINK and BRACKET_API_KEY and GOOGLE_SHEET_LINK):
        return

    matches, err = await fetch_challonge_open_matches(BRACKET_LINK, BRACKET_API_KEY)
    if err or not matches:
        return

    captains_dict, is_1v1, err2 = await fetch_google_sheet_captains(GOOGLE_SHEET_LINK)
    if err2:
        return

    cat_primary = discord.utils.get(guild.categories, id=CHANNEL_IDS.get("category_1", 1492915175836221532))
    cat_backup = discord.utils.get(guild.categories, id=CHANNEL_IDS.get("category_2", 1492915301602430996))
    if not cat_primary and not cat_backup:
        return

    helper_team_role = discord.utils.get(guild.roles, id=ROLE_IDS["helper_team"])

    for match in matches:
        team1, team2 = match['team1'], match['team2']
        p1_id, p2_id = match['player1_id'], match['player2_id']
        match_id, mod_round = match['id'], match['round']

        c1_raw = captains_dict.get(team1, "") or captains_dict.get(team1.strip(), "")
        c2_raw = captains_dict.get(team2, "") or captains_dict.get(team2.strip(), "")

        def extract_uid(raw: str):
            m = re.search(r'<@!?(\d+)>', raw)
            if m: return int(m.group(1))
            if raw.strip().isdigit(): return int(raw.strip())
            return None

        uid1, uid2 = extract_uid(c1_raw), extract_uid(c2_raw)
        captain1 = await guild.fetch_member(uid1) if uid1 else None
        captain2 = await guild.fetch_member(uid2) if uid2 else None

        if is_1v1:
            n1 = (captain1.name if captain1 else re.sub(r'[^a-zA-Z0-9]', '', team1))[:12].lower()
            n2 = (captain2.name if captain2 else re.sub(r'[^a-zA-Z0-9]', '', team2))[:12].lower()
            chan_name = f"r{mod_round}-{n1}-vs-{n2}"
        else:
            safe_t1 = re.sub(r'[^a-zA-Z0-9]', '', team1).lower()[:8]
            safe_t2 = re.sub(r'[^a-zA-Z0-9]', '', team2).lower()[:8]
            c1_sfx = captain1.name.lower()[:6] if captain1 else 'cap1'
            c2_sfx = captain2.name.lower()[:6] if captain2 else 'cap2'
            chan_name = f"r{mod_round}-{safe_t1}{c1_sfx}-vs-{safe_t2}{c2_sfx}"

        chan_name = re.sub(r'[^a-zA-Z0-9\-]', '-', chan_name)
        chan_name = re.sub(r'-+', '-', chan_name).strip('-')[:100]
        topic = f"MatchID:{match_id} | P1:{p1_id} | P2:{p2_id} | Team1:{team1} | Team2:{team2}"

        already_exists = False
        for c in filter(None, [cat_primary, cat_backup]):
            if discord.utils.get(c.channels, name=chan_name):
                already_exists = True
                break
        if already_exists: continue

        target_category = cat_primary if cat_primary and len(cat_primary.channels) < 49 else cat_backup
        
        try:
            overwrites = dict(target_category.overwrites) if target_category and target_category.overwrites else {}
            if guild.default_role not in overwrites:
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            else:
                overwrites[guild.default_role].view_channel = False

            overwrites[guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_permissions=True)
            
            for role_key in ["head_organizer", "head_helper", "helper_team"]:
                if r_id := ROLE_IDS.get(role_key):
                    if staff_r := discord.utils.get(guild.roles, id=r_id):
                        overwrites[staff_r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            if captain1: overwrites[captain1] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            if captain2: overwrites[captain2] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            new_ch = await guild.create_text_channel(
                name=chan_name,
                category=target_category,
                topic=topic,
                overwrites=overwrites
            )

            rules_embed = discord.Embed(
                title="⚓ Ghost Fleet GR — Match Setup",
                description="Welcome to your match channel. Use this channel for all tournament discussions.",
                color=discord.Color(BRAND_COLOR)
            )
            rules_embed.add_field(
                name="📋 Tournament Information",
                value=(
                    f"• 🏆 [Live Bracket]({LINK_BRACKET})\n"
                    f"• ⏰ [Deadlines]({LINK_DEADLINE})\n"
                    f"• 📜 [Rules]({LINK_RULES})"
                ),
                inline=False
            )
            
            if is_1v1:
                pval = f"**Round:** R{mod_round}\n**Captain 1:** {captain1.mention if captain1 else c1_raw or team1}\n**Captain 2:** {captain2.mention if captain2 else c2_raw or team2}"
            else:
                pval = f"**Round:** R{mod_round}\n**Team 1:** {team1} — Captain: {captain1.mention if captain1 else c1_raw or 'Not Found'}\n**Team 2:** {team2} — Captain: {captain2.mention if captain2 else c2_raw or 'Not Found'}"

            rules_embed.add_field(name="👥 Match Participants", value=pval, inline=False)
            rules_embed.add_field(
                name="🆘 Need Help?",
                value=f"Ping {helper_team_role.mention if helper_team_role else '@Helper Team'} for assistance. ⚓",
                inline=False
            )
            rules_embed.set_footer(text=f"{ORGANIZATION_NAME} • Auto-Ticket")

            ping_content = " ".join(filter(None, [
                captain1.mention if captain1 else (c1_raw or None),
                captain2.mention if captain2 else (c2_raw or None),
            ])) or f"{team1} vs {team2}"

            logo_candidates_at = ["Ghost Fleet GR logo.png", "Vᴀʟᴏʀᴀɴᴛ Vᴀɴɢᴜᴀʀᴅ E-ꜱᴩᴏʀᴛꜱ logo.png", "logo.png"]
            sent_at = False
            for lp_at in logo_candidates_at:
                try:
                    with open(lp_at, "rb") as lf:
                        rules_embed.set_thumbnail(url="attachment://logo.png")
                        await new_ch.send(content=ping_content, embed=rules_embed, file=discord.File(io.BytesIO(lf.read()), "logo.png"))
                        sent_at = True
                        break
                except FileNotFoundError:
                    continue
                except Exception:
                    break
            if not sent_at:
                await new_ch.send(content=ping_content, embed=rules_embed)

        except Exception as e:
            print(f"[auto-ticket] Channel creation error {chan_name}: {e}")

@tree.command(name='upload-bracket-result', description='Upload match result manually directly to Challonge bracket based on this ticket')
@app_commands.describe(
    winner='The captain or team representative who won the match',
    winner_score='Score of the winner',
    loser_score='Score of the loser'
)
async def upload_bracket_result(interaction: discord.Interaction, winner: discord.User, winner_score: int, loser_score: int):
    if not (has_event_create_permission(interaction) or has_event_result_permission(interaction)):
        await interaction.response.send_message("❌ Let your organizer do this.", ephemeral=True)
        return
        
    topic = getattr(interaction.channel, 'topic', '')
    if not topic or "MatchID:" not in topic:
        await interaction.response.send_message("❌ This command must be run inside a Match Ticket channel generated by the bot.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=False)
    
    match_id_match = re.search(r'MatchID:(\d+)', topic)
    p1_match = re.search(r'P1:(\d+)', topic)
    p2_match = re.search(r'P2:(\d+)', topic)
    t1_match = re.search(r'Team1:(.*?) \|', topic)
    t2_match = re.search(r'Team2:(.*)', topic)
    
    if match_id_match and p1_match and p2_match:
        m_id = match_id_match.group(1)
        p1_id = p1_match.group(1)
        p2_id = p2_match.group(1)
        
        t1_name = t1_match.group(1).strip() if t1_match else None
        t2_name = t2_match.group(1).strip() if t2_match else None
        
        captains_dict, is_1v1, _ = await fetch_google_sheet_captains(GOOGLE_SHEET_LINK)
        
        winner_p_id = p1_id # default guess
        if captains_dict and t1_name and t2_name:
            c1_mention = captains_dict.get(t1_name, "")
            c2_mention = captains_dict.get(t2_name, "")
            if str(winner.id) in c2_mention:
                winner_p_id = p2_id
            elif str(winner.id) in c1_mention:
                winner_p_id = p1_id
        
        scores_csv = f"{winner_score}-{loser_score}"
        if w_score := max(winner_score, loser_score):
            l_score = min(winner_score, loser_score)
            scores_csv = f"{w_score}-{l_score}"

        if BRACKET_LINK and BRACKET_API_KEY:
            success, challonge_err = await update_challonge_match(
                BRACKET_LINK, BRACKET_API_KEY, m_id, winner_p_id, scores_csv
            )
            if success:
                import asyncio
                await interaction.edit_original_response(content=f"🎉 **Challonge Updated Successfully!** Match ID `{m_id}` advanced.\n*(Auto-scanning for any newly unlocked matches...)*")
                asyncio.create_task(auto_create_open_tickets(interaction.guild, interaction.user))
            else:
                await interaction.edit_original_response(content=f"❌ **Challonge Update Failed:** {challonge_err}")
    else:
        await interaction.edit_original_response(content="❌ Could not extract complete Match Data from the channel topic.")

if __name__ == "__main__":
    # Get Discord token from environment
    token = os.environ.get("DISCORD_TOKEN")
    
    # Fallback method if direct get doesn't work
    if not token:
        for key, value in os.environ.items():
            if 'DISCORD' in key and 'TOKEN' in key:
                token = value
                break
    
    if not token:
        print("ERROR: Discord token not found in environment variables.")
        print("Please set your Discord bot token in the DISCORD_TOKEN environment variable.")
        print("You can also create a .env file with: DISCORD_TOKEN=your_token_here")
        exit(1)
    
    try:
        print("🚀 Starting Discord bot...")
        print("📡 Connecting to Discord...")
        bot.run(token, log_handler=None)  # Disable default logging to reduce startup time
    except discord.LoginFailure:
        print("ERROR: Invalid Discord token. Please check your bot token.")
        exit(1)
    except discord.HTTPException as e:
        print(f"ERROR: HTTP error connecting to Discord: {e}")
        exit(1)
    except Exception as e:
        print(f"ERROR: Error starting bot: {e}")
        exit(1)
