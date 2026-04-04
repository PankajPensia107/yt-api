from fastapi import FastAPI
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig

app = FastAPI()

@app.get("/")
def home():
    return {"message": "API running"}

@app.get("/summary")
def get_summary(video_id: str):
    try:
        api = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username="ccaiclkg",
                proxy_password="mbnuts1y31oi",
            )
        )

        transcript = api.fetch(video_id)

        text = " ".join([x.text for x in transcript])

        return {
            "video_id": video_id,
            "summary": text[:500]
        }

    except Exception as e:
        return {"error": str(e)}
