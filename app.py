from flask import Flask, render_template, request
from analyzer import BuildAnalyzer
import threading

app = Flask(__name__)
analyzer = BuildAnalyzer()

# Fetch champion list for autocomplete
champion_names = []
try:
    champs_data = analyzer.client.get_champion_list()
    if champs_data:
        champion_names = sorted(list(champs_data['data'].keys()))
except Exception as e:
    print(f"Error loading champions: {e}")

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    error = None
    
    if request.method == 'POST':
        champion = request.form.get('champion')
        opponent = request.form.get('opponent')
        
        if not champion:
            error = "Por favor ingresa un campeón."
        else:
            try:
                # Expanded search with better coverage for all roles
                matches = analyzer.find_matchups(champion, opponent if opponent else None, match_limit=40, max_seconds=60)
                
                if matches:
                    stats = analyzer.analyze_builds(matches, champion)
                    
                    # Format results for template
                    formatted_results = []
                    
                    # Cache version to avoid repeated API calls
                    ddragon_version = "latest"
                    try:
                        ddragon_version = analyzer.client.watcher.data_dragon.versions_for_region(analyzer.client.region)['n']['item']
                    except:
                        pass

                    for build_ids, data in stats.items():
                        winrate = (data['wins'] / data['games']) * 100
                        
                        build_items = []
                        for item_id in build_ids:
                            item_data = None
                            if analyzer.items_data and 'data' in analyzer.items_data:
                                item_data = analyzer.items_data['data'].get(str(item_id))
                            
                            if item_data:
                                build_items.append({
                                    'name': item_data['name'],
                                    'image': f"http://ddragon.leagueoflegends.com/cdn/{ddragon_version}/img/item/{item_data['image']['full']}"
                                })
                            else:
                                build_items.append({'name': str(item_id), 'image': ''})
                                
                        formatted_results.append({
                            'build_items': build_items,
                            'winrate': round(winrate, 1),
                            'wins': data['wins'],
                            'games': data['games']
                        })
                    
                    # Sort by games played (popularity)
                    formatted_results.sort(key=lambda x: x['games'], reverse=True)
                    results = formatted_results
                else:
                    error = "No se encontraron partidas recientes para este matchup."
            except Exception as e:
                print(f"Error: {e}")
                error = "La búsqueda tardó demasiado o hubo un error de conexión con Riot. Inténtalo de nuevo."

    return render_template('index.html', 
                          results=results, 
                          error=error, 
                          champions=champion_names,
                          searched_champion=request.form.get('champion') if request.method == 'POST' else None,
                          searched_opponent=request.form.get('opponent') if request.method == 'POST' else None)

if __name__ == '__main__':
    import os
    # Use PORT from environment (Render sets this automatically)
    port = int(os.getenv('PORT', 5001))
    # debug=False for production
    app.run(debug=False, host='0.0.0.0', port=port)
