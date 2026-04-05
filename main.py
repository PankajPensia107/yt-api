from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
import shutil
import os
import uuid

import pytesseract
from PIL import Image
import pdfplumber
from pdf2image import convert_from_path
from docx import Document
import textract
import cv2

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Multi-language OCR config
OCR_LANG = "eng+hin+pan"
OCR_CONFIG = "--oem 3 --psm 6"


# ---------- IMAGE PREPROCESSING ----------
def preprocess_image(file_path):
    img = cv2.imread(file_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # noise removal + threshold
    gray = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    return thresh


def extract_from_image(file_path):
    processed = preprocess_image(file_path)
    return pytesseract.image_to_string(
        processed,
        lang=OCR_LANG,
        config=OCR_CONFIG
    )


# ---------- PDF ----------
def extract_from_pdf(file_path):
    text = ""

    # Try text-based PDF first
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except:
        pass

    # If no text → OCR
    if not text.strip():
        images = convert_from_path(file_path, dpi=200)

        for img in images:
            text += pytesseract.image_to_string(
                img,
                lang=OCR_LANG,
                config=OCR_CONFIG
            )

    return text


# ---------- DOCX ----------
def extract_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs])


# ---------- DOC ----------
def extract_from_doc(file_path):
    text = textract.process(file_path)
    return text.decode("utf-8", errors="ignore")


# ---------- BACKGROUND TASK ----------
def process_file(file_path, ext, task_id):
    try:
        if ext in ["jpg", "jpeg", "png", "bmp", "gif", "webp"]:
            text = extract_from_image(file_path)

        elif ext == "pdf":
            text = extract_from_pdf(file_path)

        elif ext == "docx":
            text = extract_from_docx(file_path)

        elif ext == "doc":
            text = extract_from_doc(file_path)

        else:
            text = "Unsupported file type"

        # Save result
        with open(f"{UPLOAD_DIR}/{task_id}.txt", "w", encoding="utf-8") as f:
            f.write(text)

    except Exception as e:
        with open(f"{UPLOAD_DIR}/{task_id}.txt", "w", encoding="utf-8") as f:
            f.write(f"Error: {str(e)}")


# ---------- API ----------
@app.post("/extract")
async def extract(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):

    task_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ext = file.filename.split(".")[-1].lower()

    # Large file → background processing
    if ext == "pdf":
        background_tasks.add_task(process_file, file_path, ext, task_id)
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Large file, processing in background"
        }

    try:
        if ext in ["jpg", "jpeg", "png", "bmp", "gif", "webp"]:
            text = extract_from_image(file_path)

        elif ext == "docx":
            text = extract_from_docx(file_path)

        elif ext == "doc":
            text = extract_from_doc(file_path)

        else:
            return JSONResponse(
                {"error": "Unsupported file type"},
                status_code=400
            )

        return {
            "filename": file.filename,
            "filetype": ext,
            "extracted_text": text.strip()
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------- RESULT CHECK ----------
@app.get("/result/{task_id}")
def get_result(task_id: str):
    result_file = f"{UPLOAD_DIR}/{task_id}.txt"

    if not os.path.exists(result_file):
        return {"status": "processing"}

    with open(result_file, "r", encoding="utf-8") as f:
        data = f.read()

    return {
        "status": "completed",
        "text": data
    }
