import json
from pprint import pprint

import requests


def get_data():
    data_no_json = requests.get("https://coursemc.ru/api/v1/student/").text
    data = json.loads(data_no_json)
    return data
