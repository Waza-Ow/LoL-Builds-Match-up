from riotwatcher import LolWatcher, ApiError
import os

class RiotClient:
    def __init__(self):
        self.watcher = LolWatcher(config.RIOT_API_KEY)
        self.region = config.REGION

    def get_champion_list(self):
        """Fetches the latest version of champion list."""
        try:
            versions = self.watcher.data_dragon.versions_for_region(self.region)
            champions_version = versions['n']['champion']
            current_champ_list = self.watcher.data_dragon.champions(champions_version)
            return current_champ_list
        except ApiError as err:
            print(f"Error fetching champions: {err}")
            return None

    def get_items(self):
        """Fetches the latest version of item list in Spanish (LAS/LAN)."""
        try:
            versions = self.watcher.data_dragon.versions_for_region(self.region)
            items_version = versions['n']['item']
            # 'es_MX' is typically used for Latin America in Riot API
            return self.watcher.data_dragon.items(items_version, locale='es_MX')
        except ApiError as err:
            print(f"Error fetching items: {err}")
            return None

    def get_summoner_by_name(self, name):
        try:
            return self.watcher.summoner.by_name(self.region, name)
        except ApiError as err:
            print(f"Error fetching summoner: {err}")
            return None

    def get_challenger_league(self, queue="RANKED_SOLO_5x5"):
        try:
            return self.watcher.league.challenger_by_queue(self.region, queue)
        except ApiError as err:
            print(f"Error fetching challenger league: {err}")
            return None
    
    def get_grandmaster_league(self, queue="RANKED_SOLO_5x5"):
        try:
            return self.watcher.league.grandmaster_by_queue(self.region, queue)
        except ApiError as err:
            print(f"Error fetching grandmaster league: {err}")
            return None
    
    def get_master_league(self, queue="RANKED_SOLO_5x5"):
        try:
            return self.watcher.league.masters_by_queue(self.region, queue)
        except ApiError as err:
            print(f"Error fetching master league: {err}")
            return None
    
    def get_high_elo_players(self, queue="RANKED_SOLO_5x5"):
        """Combines Challenger, Grandmaster, and top Master players for a larger pool."""
        import random
        all_entries = []
        
        print("Fetching high elo players...")
        challenger = self.get_challenger_league(queue)
        if challenger and 'entries' in challenger:
            all_entries.extend(challenger['entries'])
            print(f"  Challenger: {len(challenger['entries'])} players")
        
        grandmaster = self.get_grandmaster_league(queue)
        if grandmaster and 'entries' in grandmaster:
            all_entries.extend(grandmaster['entries'])
            print(f"  Grandmaster: {len(grandmaster['entries'])} players")
        
        # Master has too many players (10k+), take only top 500
        master = self.get_master_league(queue)
        if master and 'entries' in master:
            master_entries = master['entries'][:500]  # Limit to top 500
            all_entries.extend(master_entries)
            print(f"  Master (top 500): {len(master_entries)} players")
        
        # Shuffle to get variety from all tiers
        random.shuffle(all_entries)
        print(f"  Total pool: {len(all_entries)} players\n")
        return all_entries

    def get_match_ids(self, puuid, count=20):
        try:
            return self.watcher.match.matchlist_by_puuid(self.region, puuid, count=count)
        except ApiError as err:
            print(f"Error fetching match IDs: {err}")
            return None

    def get_match_details(self, match_id):
        try:
            return self.watcher.match.by_id(self.region, match_id)
        except ApiError as err:
            print(f"Error fetching match details: {err}")
            return None

    def get_champion_mastery(self, puuid, champion_id):
        try:
            return self.watcher.champion_mastery.by_puuid_by_champion(self.region, puuid, champion_id)
        except ApiError as err:
            # 404 means no mastery (never played or not found)
            if err.response.status_code != 404:
                print(f"Error fetching mastery: {err}")
            return None

if __name__ == "__main__":
    client = RiotClient()
    # Test challenger fetch
    challengers = client.get_challenger_league()
    if challengers:
        print(f"Fetched {len(challengers['entries'])} challenger players.")
        if challengers['entries']:
            first_entry = challengers['entries'][0]
            print(f"Entry keys: {first_entry.keys()}")
            # Fallback or correct key usage
            s_name = first_entry.get('summonerName', 'Unknown')
            s_id = first_entry.get('summonerId')
            print(f"Example player: {s_name} (ID: {s_id})")
            
            # Test match fetch for first player
            # Note: We need PUUID. If summonerName is missing/empty, we might need to fetch by summonerId to get PUUID
            if s_id:
                try:
                    summoner = client.watcher.summoner.by_id(client.region, s_id)
                    if summoner:
                        matches = client.get_match_ids(summoner['puuid'], count=1)
                        if matches:
                            print(f"Fetched match ID: {matches[0]}")
                            details = client.get_match_details(matches[0])
                            if details:
                                print("Successfully fetched match details.")
                except ApiError as e:
                    print(f"Error fetching summoner by ID: {e}")


