from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
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

# ---------- CORS SETTINGS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Default config: PSM 3 paragraph reading ke liye better hai PSM 6 se
OCR_CONFIG = "--oem 3 --psm 3"

# ---------- IMAGE PREPROCESSING (Improved) ----------
def preprocess_image(file_path):
    img = cv2.imread(file_path)
    if img is None: return None
    
    # Image ko grayscale karna
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Adaptive Thresholding: Ye low light/shadowy photos ke liye best hai
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Noise kam karna bina text kharab kiye
    kernel = np.ones((1, 1), np.uint8)
    processed = cv2.dilate(thresh, kernel, iterations=1)
    processed = cv2.erode(processed, kernel, iterations=1)
    
    return processed

def extract_from_image(file_path, lang):
    processed = preprocess_image(file_path)
    if processed is None: return "Error: Image not readable"
    
    return pytesseract.image_to_string(processed, lang=lang, config=OCR_CONFIG)

# ---------- PDF ----------
def extract_from_pdf(file_path, lang):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
    except: pass

    if not text.strip():
        # Scanned PDF ke liye DPI 150 (Balance between quality and RAM)
        images = convert_from_path(file_path, dpi=150)
        for img in images:
            text += pytesseract.image_to_string(img, lang=lang, config=OCR_CONFIG)
    return text

# ---------- BACKGROUND TASK ----------
def process_file_async(file_path, ext, task_id, lang):
    try:
        if ext in ["jpg", "jpeg", "png", "bmp", "gif", "webp"]:
            text = extract_from_image(file_path, lang)
        elif ext == "pdf":
            text = extract_from_pdf(file_path, lang)
        elif ext == "docx":
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        else:
            text = "Unsupported file type"

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
async def extract(
    file: UploadFile = File(...), 
    lang: str = Form("eng"), # Default language English rakhi hai
    background_tasks: BackgroundTasks = None
):
    task_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1].lower()
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    # Language validation (Sirf wahi lang jo installed hain)
    valid_langs = ["eng", "hin", "pan", "eng+hin", "eng+pan", "eng+hin+pan"]
    if lang not in valid_langs:
        lang = "eng" # Fallback to English

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(process_file_async, file_path, ext, task_id, lang)
    
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
    
    return {
        "status": "completed",
        "text": data
    }
