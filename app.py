from fastapi import FastAPI
from youtube_transcript_api import YouTubeTranscriptApi
import random

app = FastAPI()

# 🔁 Your proxy list
proxies_list = [
    "http://ccaiclkg:mbnuts1y31oi@31.59.20.176:6754",
    "http://ccaiclkg:mbnuts1y31oi@23.95.150.145:6114",
    "http://ccaiclkg:mbnuts1y31oi@198.23.239.134:6540",
    "http://ccaiclkg:mbnuts1y31oi@45.38.107.97:6014",
    "http://ccaiclkg:mbnuts1y31oi@107.172.163.27:6543",
]

@app.get("/")
def home():
    return {"message": "API running"}

@app.get("/summary")
def get_summary(video_id: str):
    last_error = None

    # 🔁 Try multiple proxies
    for i in range(5):
        proxy = random.choice(proxies_list)

        try:
            api = YouTubeTranscriptApi(
                proxies={
                    "http": proxy,
                    "https": proxy,
                }
            )

            transcript = api.fetch(video_id)
            text = " ".join([x.text for x in transcript])

            return {
                "video_id": video_id,
                "proxy_used": proxy,
                "summary": text[:500]
            }

        except Exception as e:
            last_error = str(e)
            continue

    return {
        "error": "All proxies failed",
        "details": last_error
    }
