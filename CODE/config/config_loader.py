import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "network.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = json.load(file)

    return config