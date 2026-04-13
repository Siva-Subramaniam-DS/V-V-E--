import json
import os

CONFIG_FILE = "bot_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)

config = load_config()

# Global Roles & Channels (pulled from config)
ROLE_IDS = {
    "head_organizer": config.get("roles", {}).get("head_organizer", 1457369462931062947),
    "head_helper":    config.get("roles", {}).get("head_helper", 1492730906056855773),  # tour helper
    "helper_team":    config.get("roles", {}).get("helper_team", 1492730906056855773),
    "judge":          config.get("roles", {}).get("judge", 1492727793631498351),
    "recorder":       config.get("roles", {}).get("recorder", 1492727854406959115),
    "staff":          config.get("roles", {}).get("staff", 1492727567554183318),
}

CHANNEL_IDS = {
    "schedule":     config.get("channels", {}).get("schedule", 1492565951886135577),
    "results":      config.get("channels", {}).get("results", 1492565931522785511),
    "transcripts":  config.get("channels", {}).get("transcripts", 1492565906046455949),
    "attendance":   config.get("channels", {}).get("attendance", 1175583811812204565),  # unchanged
    "announcement":  config.get("channels", {}).get("announcement", 1492564923031748688),
    "tour_chat":    config.get("channels", {}).get("tour_chat", 1492565999721910434),
    "registration": config.get("channels", {}).get("registration", 1492569389399150592),
    "rules":        config.get("channels", {}).get("rules", 1492565754137149491),
    "bracket":      config.get("channels", {}).get("bracket", 1492565717633990919),
    "deadlines":    config.get("channels", {}).get("deadlines", 1492565975847932104),
    "participants_list": config.get("channels", {}).get("participants_list", 1492565809631989904),
    "event_videos": config.get("channels", {}).get("event_videos", 1492722253417283644),
    "category_1":   config.get("channels", {}).get("category_1", 1492915175836221532),
    "category_2":   config.get("channels", {}).get("category_2", 1492915301602430996),
    "closed_tickets_category": config.get("channels", {}).get("closed_tickets_category", 1492915418556268605),
}

ORGANIZATION_NAME = config.get("organization_name", "Vᴀʟᴏʀᴀɴᴛ Vᴀɴɢᴜᴀʀᴅ E-ꜱᴩᴏʀᴛꜱ")
TOURNAMENT_SYSTEM_NAME = config.get("tournament_system_name", "Vᴀʟᴏʀᴀɴᴛ Vᴀɴɢᴜᴀʀᴅ E-ꜱᴩᴏʀᴛꜱ Tournament System")

# Active tournament properties
BRACKET_LINK = config.get("bracket_link", "")
BRACKET_API_KEY = config.get("bracket_api_key", "")
GOOGLE_SHEET_LINK = config.get("google_sheet_link", "")
CURRENT_TOURNAMENT_NAME = config.get("tournament_name", "Undefined")
EVENTS_FILE = "events.json"
RULES_FILE = "tournament_rules.json"
