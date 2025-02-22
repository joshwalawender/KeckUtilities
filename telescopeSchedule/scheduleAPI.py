import requests
import json
import yaml


def query_telescope_schedule(route, query):
    url = f"https://vm-appserver.keck.hawaii.edu/api/schedule/{route}?{query}"
    print('Querying telescope schedule')
    r = requests.get(url)
    return json.loads(r.text)


def get_routes():
    url = 'https://vm-appserver.keck.hawaii.edu/schedule/swagger/schedule_api.yaml'
    try:
        r = requests.get(url)
        result = yaml.safe_load(r.text)
        routes_data = result.get('paths')
    except:
        print('Failed to get list of routes')
        routes = []
    for route in routes_data.keys():
        print(route)
#         print(routes[route])
#         print()
    return [r for r in routes_data.keys()], routes_data
