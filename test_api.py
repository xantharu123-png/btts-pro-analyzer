import requests

api_key = "DEIN_API_KEY"  # Dein echter Key!

response = requests.get(
    "https://v3.football.api-sports.io/fixtures",
    headers={"x-apisports-key": api_key},
    params={
        'league': 78,
        'live': 'all',
        'season': 2024
    }
)

print(response.status_code)
print(response.json())