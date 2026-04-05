from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import pytesseract
import io

# Fix path for Render/Linux
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

app = FastAPI()

@app.get("/")
def home():
    return {"message": "OCR API is running 🚀"}

@app.post("/extract-text/")
async def extract_text(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        text = pytesseract.image_to_string(image)

        return JSONResponse({
            "filename": file.filename,
            "text": text
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
