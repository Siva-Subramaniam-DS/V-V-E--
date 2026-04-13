import requests
import asyncio
import re
import csv
import io

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
        for i, h in enumerate(h_lower):
            if 'team' in h or 'discord name' in h or 'participant' in h:
                key_col = i
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
        return captains, None
    except Exception as e:
        return None, str(e)

async def fetch_google_sheet_captains(sheet_link: str):
    """Async wrapper — runs the HTTP call in a thread so the event loop stays free."""
    return await asyncio.to_thread(_sync_fetch_google_sheet_captains, sheet_link)

