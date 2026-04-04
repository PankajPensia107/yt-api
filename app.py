from fastapi import FastAPI
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

app = FastAPI()

@app.get("/summary")
def get_summary(video_id: str):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([x['text'] for x in transcript])

        return {
            "video_id": video_id,
            "summary": text[:500]
        }

    except TranscriptsDisabled:
        return {"error": "Transcripts are disabled for this video"}

    except NoTranscriptFound:
        return {"error": "No transcript found for this video"}

    except Exception as e:
        return {"error": str(e)}
