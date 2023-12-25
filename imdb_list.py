import requests
import html
import json
import configparser
import csv
from utils import find_collection_with_name_or_create, get_all_collections

# Load Config
config = configparser.ConfigParser()
config.read('config.ini')
server_url = config["main"]["server_url"]
user_id = config["main"]["user_id"]
imdb_list_ids = json.loads(config["main"]["imdb_list_ids"])
headers = {'X-Emby-Token': config["main"]["jellyfin_api_key"]}

# Creating a session for persistent connections
session = requests.Session()
session.headers.update(headers)

params = {
    "enableTotalRecordCount": "false",
    "enableImages": "false",
    "Recursive": "true"
}

imdb_to_jellyfin_type_map = {
    "movie": ["Movie"],
    "short": ["Movie"],
    "podcastSeries": ["Podcast"],
    "tvEpisode": ["TvProgram", "Episode"],
    "tvSpecial": ["TvProgram", "Episode", "Program"],
    "tvSeries": ["Program", "Series"],
    "tvShort": ["TvProgram", "Episode", "Program"],
    "tvMiniSeries": ["Program", "Series"],
    "tvMovie": ["Movie", "TvProgram", "Episode"],
    "videoGame": ["Movie", "TvProgram", "Program"],
    "video": ["Movie", "TvProgram", "Episode", "Series"],
}

# Find list of all collections
collections = get_all_collections(headers=headers)

for imdb_list_id in imdb_list_ids:
    # Fetching the IMDB list
    list_page_response = session.get(f'https://www.imdb.com/list/{imdb_list_id}')
    list_name = html.unescape(list_page_response.text.split('<h1 class="header list-name">')[1].split("</h1>")[0])
    collection_id = find_collection_with_name_or_create(list_name, collections, headers=headers)
    print("************************************************")
    print()

    # Fetching the export list
    export_response = session.get(f'https://www.imdb.com/list/{imdb_list_id}/export')
    reader = csv.DictReader(export_response.text.split("\n"))
    
    for item in reader:
        params2 = params.copy()
        params2["searchTerm"] = item["Title"]
        params2["years"] = item["Year"]

        if item["Title Type"] == "tvEpisode" and ": " in item["Title"]:
            params2["searchTerm"] = item["Title"].split(": ", 1)[1]

        if config.getboolean("main", "disable_tv_year_filter", fallback=False) and item["Title Type"] in ["tvSeries", "tvMiniSeries"]:
            del params2["years"]

        params2["includeItemTypes"] = imdb_to_jellyfin_type_map[item["Title Type"]]
        res2 = session.get(f'{server_url}/Users/{user_id}/Items', params=params2)
        try:
            if len(res2.json()["Items"]) > 0:
                item_id = res2.json()["Items"][0]["Id"]
                session.post(f'{server_url}/Collections/{collection_id}/Items?ids={item_id}')
                print("Added", item["Title"], item_id)
            else:
                print("Can't find", item["Title"])
        except json.decoder.JSONDecodeError:
            print("JSON decode error - skipping")

# Closing the session
session.close()
