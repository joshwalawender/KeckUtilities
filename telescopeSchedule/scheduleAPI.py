import requests
import json


def query_telescope_schedule(route, query):
    url = f"https://vm-appserver.keck.hawaii.edu/api/schedule/{route}?{query}"
    print('Querying telescope schedule')
    r = requests.get(url)
    return json.loads(r.text)


def get_routes():
    url = 'https://vm-appserver.keck.hawaii.edu/schedule/swagger/schedule_api.yaml'
    try:
        r = requests.get(url)
        result = json.loads(r.text)
        routes = result.get('paths')
    except:
        print('Failed to get list of routes')
        routes = []
    for route in routes:
        print(route)
    return routes
