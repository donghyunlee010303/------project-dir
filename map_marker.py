# (If needed, install python-dotenv manually in your environment before running this script)

import os
try:
    from dotenv import load_dotenv
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "python-dotenv"])
    from dotenv import load_dotenv
import requests
import re
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import json

# %%
# Load environment variables from .env file
load_dotenv()

# Access the environment variables
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
DATABASE_ID = os.getenv('DATABASE_ID')
KAKAOMAP_JS_KEY = os.getenv('KAKAOMAP_JS_KEY')
KAKAOMAP_REST_API_KEY = os.getenv('KAKAOMAP_REST_API_KEY')
NAVERMAP_CLIENT_ID = os.getenv('NAVERMAP_CLIENT_ID')
NAVERMAP_CLIENT_SECRET = os.getenv('NAVERMAP_CLIENT_SECRET')

# %%
KAKAOMAP_JS_KEY

# %% [markdown]
# # 메인 코드
# 
# ### 노션 db에서 url을 가져오는 함수 정의
# 얘를 반복문을 사용하여 리스트에 append하고, 이를 api 사용하여 html 스크립트에 마커로 표시하는 로직을 사용할 것

# %%
# 노션 db에서 url을 가져오는 함수

def get_notion_urls():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers) 
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    data = response.json()
    urls = []
    for page in data['results']:
        if 'URL' in page['properties']:
            url = page['properties']['URL']['url']
            if url and isinstance(url, str) and url.startswith("http"):
                urls.append(url)
    return urls

# %%
get_notion_urls()

# %% [markdown]
# ### 단축 url -> (위도, 경도) 함수 정의

# %%
# 단축 url을 처리하는 함수
# 여기에 실행 함수까지 같이 추가를 해야함 (위도경도 가져오기? 네이버/카카오 각각 별도로) -> 이후 다른 함수에서 위도경도를 사용하여 마커로 표시하도록

def get_url_coords(link: str):
    if 'kakao' in link:
        try:
            response = requests.get(link, allow_redirects=True, timeout=5)
            link = response.url # 최종 redirection된 url로 교체
        except requests.RequestException as e:
            print(f"Error fetching link: {e}")
            return None
        
        parsed_url = urlparse(link)
        qs = parse_qs(parsed_url.query)
        item_id = int(qs['itemId'][0])
        # return item_id

        url = f"https://place.map.kakao.com/{item_id}"
        headers = {
            'Referer': 'https://map.kakao.com/',
            'User-Agent': 'Mozilla/5.0',
        }

        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            raise Exception(f"요청 실패: {res.status_code}")

        soup = BeautifulSoup(res.text, 'html.parser')
        
        # <meta property="og:image" ...> 찾기
        meta_tag = soup.find("meta", {"property": "og:image"})
        if not meta_tag or "content" not in meta_tag.attrs:
            raise Exception("og:image 메타 태그를 찾을 수 없습니다.")
        
        content_url = meta_tag["content"]
        
        # 정규표현식으로 m=경도,위도 추출
        match = re.search(r"m=([0-9.]+)%2C([0-9.]+)", content_url)
        if not match:
            raise Exception("좌표 정보(m=...)를 찾을 수 없습니다.")
        
        lng, lat = map(float, match.groups())
        
        return (lat, lng)

    elif 'naver' in link:
        try:
            response = requests.get(link, allow_redirects=True, timeout=5)
            link = response.url # 최종 redirection된 url로 교체
        except requests.RequestException as e:
            print(f"Error fetching link: {e}")
            return None
        
        item_id = re.search(r'place/(\d+)', link)
        item_id = item_id.group(1)
        # return item_id

        url = f"https://map.naver.com/p/api/place/summary/{item_id}"
        headers = {
        'Referer': 'https://map.naver.com/',
        'User-Agent': 'Mozilla/5.0',
        }

        res = requests.get(url, headers=headers)
        data = res.json()
        #print(data)

        lat = float(data['data']['nmapSummaryBusiness']['y'])  # 위도
        lng = float(data['data']['nmapSummaryBusiness']['x'])  # 경도
        
        return (lat, lng)

    else:
        print("Unsupported URL type: ", link)
        return None

# %%
get_url_coords("https://naver.me/xGI191mm")

# %% [markdown]
# # 카카오맵 js에 위경도를 이용하여 마커로 표시하는 코드

# %% [markdown]
# 위의 함수를 이용하여 json 파일 생성

# %%
# 기존 markers.json 경로 설정
json_path = os.path.join(os.path.dirname(__file__), "markers.json")

# 기존 데이터 로딩 or 데이터가 없는 경우 초기화
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if "positions" not in data:
                data["positions"] = []
        except json.JSONDecodeError:
            data = {"positions": []}
else:
    data = {"positions": []}

# 기존 좌표를 (lat, lng) 튜플로 set 생성
existing_set = {(p["lat"], p["lng"]) for p in data["positions"]}

# positions 리스트에 추가할 새 결과 저장용
new_positions = []

# 위도/경도 수집
all_urls = get_notion_urls()  # 이건 리스트 형태로 리턴됨

for url in all_urls:
    try:
        coords = get_url_coords(url)
        if coords:
            lat, lng = coords
            if (lat, lng) not in existing_set:
                new_positions.append({"lat": lat, "lng": lng})
                existing_set.add((lat, lng)) # 중복 방지를 위해 set에도 추가
                print(f"URL: {url} -> Coordinates: {coords}")
            else:
                print(f"Coordinates already exist for URL: {url}")
        else:
            print(f"Failed to get coordinates for URL: {url}")
    except Exception as e:
        print(f"Error processing URL '{url}': {e}")

# 기존 데이터에 병합
data["positions"].extend(new_positions)

# 한 번에 저장
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Total markers added to json: {len(new_positions)}")

# %% [markdown]
# 마커 클러스터러 사용 -> json>html 파일 생성


