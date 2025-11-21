import time
from api_client import RiotClient

class BuildAnalyzer:
    def __init__(self):
        self.client = RiotClient()
        self.cache_matches = set()
        self.items_data = self.client.get_items()
        self.champions_data = self.client.get_champion_list()
        
        if self.items_data:
            print("Item data loaded.")
        else:
            print("Warning: Could not load item data.")

    def get_item_name(self, item_id):
        if not self.items_data:
            return str(item_id)
        
        # DataDragon items are keyed by string ID
        item = self.items_data['data'].get(str(item_id))
        return item['name'] if item else str(item_id)

    def get_champion_id(self, champion_name):
        """Resolves champion name to ID (key)."""
        if not self.champions_data:
            return None
        
        # DataDragon champions are keyed by ID (e.g. "Aatrox"), but we need the integer key for matchlist
        # Actually, DataDragon 'data' is keyed by ID string (e.g. "MonkeyKing"), 
        # and the value contains 'key' which is the integer string (e.g. "62").
        
        # Normalize input name
        name_lower = champion_name.lower().replace(" ", "")
        
        for champ_id, data in self.champions_data['data'].items():
            if data['name'].lower().replace(" ", "") == name_lower or champ_id.lower() == name_lower:
                return int(data['key'])
        return None

    def find_matchups(self, target_champ, opponent_champ=None, match_limit=40, max_seconds=60):
        """
        Scans high elo players (Master+) for matches containing the specific matchup.
        Uses Champion Mastery to filter players who have played the champ recently.
        """
        start_time = time.time()
        
        # Resolve target champion to ID for filtering
        target_champ_id = self.get_champion_id(target_champ)
        if not target_champ_id:
            print(f"Could not find ID for champion: {target_champ}")
            return []
            
        mode = f"vs {opponent_champ}" if opponent_champ else "(Any Opponent)"
        print(f"\nSearching for {target_champ} (ID: {target_champ_id}) {mode}...")
        
        # Get combined Master, Grandmaster, and Challenger players
        high_elo_entries = self.client.get_high_elo_players()
        if not high_elo_entries:
            print("No high elo players found")
            return []

        relevant_matches = []
        checked_players = 0
        max_players = 150  # Increased from 100 for better coverage
        
        # Shuffle to get random sample from different tiers
        import random
        random.shuffle(high_elo_entries)
        
        for entry in high_elo_entries:
            # Check timeout
            if time.time() - start_time > max_seconds:
                print(f"Time limit reached after checking {checked_players} players")
                break
                
            if checked_players >= max_players:
                break

            puuid = entry.get('puuid')
            if not puuid:
                continue
            
            checked_players += 1
            
            # SMART SEARCH: Check mastery first
            mastery = self.client.get_champion_mastery(puuid, target_champ_id)
            if not mastery:
                continue
                
            last_play_time = mastery.get('lastPlayTime', 0)
            current_time_ms = int(time.time() * 1000)
            # 30 days in ms - increased window for better coverage
            if current_time_ms - last_play_time > 2592000000:  # 30 days
                continue
                
            # Fetch matches for this player
            matches = self.client.get_match_ids(puuid, count=15)
            if not matches:
                continue

            for match_id in matches:
                # Check timeout inside inner loop
                if time.time() - start_time > max_seconds:
                    break

                if match_id in self.cache_matches:
                    continue
                self.cache_matches.add(match_id)

                details = self.client.get_match_details(match_id)
                if not details:
                    continue
                
                # Check game duration - only consider games longer than 20 minutes
                game_duration = details['info'].get('gameDuration', 0)
                if game_duration < 1200:  # 20 minutes in seconds
                    continue
                
                if self._is_matchup_present(details, target_champ, opponent_champ):
                    print(f"Match found! {match_id} ({game_duration//60}min)")
                    relevant_matches.append(details)
                    if len(relevant_matches) >= match_limit:
                        print(f"\nFound {len(relevant_matches)} quality matches!")
                        return relevant_matches
                
                # Basic rate limiting
                time.sleep(0.05) 
        
        print(f"\nSearch complete: {len(relevant_matches)} matches from {checked_players} players")
        return relevant_matches

    def _is_matchup_present(self, match_details, target_champ, opponent_champ):
        """Checks if both champions are in the game and on opposite teams."""
        participants = match_details['info']['participants']
        
        target_team = None
        opponent_team = None
        opponent_found = False

        for p in participants:
            if p['championName'].lower() == target_champ.lower():
                target_team = p['teamId']
            if opponent_champ and p['championName'].lower() == opponent_champ.lower():
                opponent_team = p['teamId']
                opponent_found = True
        
        if target_team is None:
            return False
            
        if opponent_champ:
            return opponent_found and target_team != opponent_team
        
        return True

    def is_completed_item(self, item_id):
        """
        Checks if an item is 'completed' (not a component).
        Heuristic: Depth >= 3 OR (Depth == 2 AND is Boot).
        """
        if not self.items_data:
            return True # Fallback if no data
            
        item = self.items_data['data'].get(str(item_id))
        if not item:
            return True
            
        depth = item.get('depth', 1)
        tags = item.get('tags', [])
        
        # Depth 3+ are usually legendary/mythic
        if depth >= 3:
            return True
            
        # Depth 2 Boots are "completed" for that slot (e.g. Berserker's Greaves)
        if depth == 2 and 'Boots' in tags:
            return True
            
        return False

    def is_valid_build(self, build, item_id):
        """Check if adding this item makes a valid 'complete' build."""
        # Filter out support/ward items
        support_items = {3858, 3859, 3860, 3862, 3863, 3864, 3865, 3866, 3867, 3868, 3869, 3870,  # Support items
                        2055, 3340, 3363, 3364, 2065}  # Wards and trinkets
        
        if item_id in support_items:
            return False
        
        return True
    
    def analyze_builds(self, matches, target_champ):
        """Aggregates winrates by item builds, filtering for quality builds."""
        build_stats = {}

        for match in matches:
            participants = match['info']['participants']
            try:
                target_p = next(p for p in participants if p['championName'].lower() == target_champ.lower())
            except StopIteration:
                continue
            
            # Extract full build (items 0-5)
            build = []
            for i in range(6):
                item_id = target_p.get(f'item{i}')
                if item_id and item_id != 0:
                    # Filter for completed items only and exclude support items
                    if self.is_completed_item(item_id) and self.is_valid_build(build, item_id):
                        build.append(item_id)
            
            # Require at least 4 completed items for a "serious" build
            if len(build) < 4:
                continue
            
            # Sort to ignore order, convert to tuple for dict key
            build_key = tuple(sorted(build)) 
            
            if build_key not in build_stats:
                build_stats[build_key] = {'wins': 0, 'games': 0}
            
            build_stats[build_key]['games'] += 1
            if target_p['win']:
                build_stats[build_key]['wins'] += 1

        return build_stats

if __name__ == "__main__":
    analyzer = BuildAnalyzer()
    
    # Try a very popular champion to ensure we find matches
    target = "Jinx"
    print(f"--- Starting Analysis for {target} ---")
    
    # Fallback: Find ANY match with the target
    matches = analyzer.find_matchups(target, opponent_champ=None, match_limit=5)
    
    if matches:
        print(f"\nFound {len(matches)} matches. Analyzing builds...")
        stats = analyzer.analyze_builds(matches, target)
        
        print("\nBuild Statistics:")
        for build, data in stats.items():
            winrate = (data['wins'] / data['games']) * 100
            
            # Translate IDs to names
            item_names = [analyzer.get_item_name(i) for i in build]
            build_str = ", ".join(item_names)
            
            print(f"Build: [{build_str}] | Winrate: {winrate:.1f}% ({data['wins']}/{data['games']})")
    else:
        print("No matches found for this champion in the sample.")
