import requests

url = "https://api.opendota.com/api/explorer"

sql = """
SELECT
    lobby_type,
    COUNT(*) AS games
FROM public_matches
GROUP BY lobby_type
ORDER BY lobby_type
"""

resp = requests.get(
    url,
    params={"sql": sql},
    timeout=60,
)

resp.raise_for_status()

data = resp.json()

print(data)
