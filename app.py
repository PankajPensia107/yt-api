from fastapi import FastAPI
from youtube_transcript_api import YouTubeTranscriptApi

app = FastAPI()

@app.get("/")
def home():
    return {"message": "API running"}

@app.get("/summary")
def get_summary(video_id: str):
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    text = " ".join([x['text'] for x in transcript])
    return {"summary": text[:500]}