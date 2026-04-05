from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import pytesseract
from PIL import Image
import pdfplumber
from pdf2image import convert_from_path
from docx import Document
import cv2
import numpy as np

app = FastAPI()

# ---------- CORS SETTINGS (CORS Error Fix) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Render/Linux me /tmp folder sabse best hota hai temporary files ke liye
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

OCR_LANG = "eng+hin+pan"
OCR_CONFIG = "--oem 3 --psm 6"

# ---------- IMAGE PREPROCESSING ----------
def preprocess_image(file_path):
    img = cv2.imread(file_path)
    if img is None: return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return thresh

def extract_from_image(file_path):
    processed = preprocess_image(file_path)
    if processed is None: return "Error: Could not process image"
    return pytesseract.image_to_string(processed, lang=OCR_LANG, config=OCR_CONFIG)

# ---------- PDF ----------
def extract_from_pdf(file_path):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
    except: pass

    if not text.strip():
        # Scanned PDF ke liye
        images = convert_from_path(file_path, dpi=100) # DPI kam rakha hai RAM bachane ke liye
        for img in images:
            text += pytesseract.image_to_string(img, lang=OCR_LANG, config=OCR_CONFIG)
    return text

# ---------- BACKGROUND TASK ----------
def process_file_async(file_path, ext, task_id):
    try:
        if ext in ["jpg", "jpeg", "png", "bmp", "gif", "webp"]:
            text = extract_from_image(file_path)
        elif ext == "pdf":
            text = extract_from_pdf(file_path)
        elif ext == "docx":
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        else:
            text = "Unsupported file type"

        # Result save karein
        result_path = os.path.join(UPLOAD_DIR, f"{task_id}.txt")
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        with open(os.path.join(UPLOAD_DIR, f"{task_id}.txt"), "w", encoding="utf-8") as f:
            f.write(f"Error: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# ---------- API ENDPOINTS ----------

@app.post("/extract")
async def extract(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    task_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1].lower()
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Background task hamesha chalao taaki frontend wait na kare
    background_tasks.add_task(process_file_async, file_path, ext, task_id)
    
    return {
        "task_id": task_id,
        "status": "processing"
    }

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    result_file = os.path.join(UPLOAD_DIR, f"{task_id}.txt")
    
    if not os.path.exists(result_file):
        return {"status": "processing"}

    with open(result_file, "r", encoding="utf-8") as f:
        data = f.read()
    
    # Result bhejne ke baad file delete kar do taaki storage na bhare
    # os.remove(result_file) 
    
    return {
        "status": "completed",
        "text": data
    }
