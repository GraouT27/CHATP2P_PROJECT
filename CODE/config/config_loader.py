import json

def load_config():
    with open ("config/network.json", "r", encoding="utf-8") as file:
        config = json.load(file)

    return config