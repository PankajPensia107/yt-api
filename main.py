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
import cv2
import numpy as np

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Multi-language OCR config
# Dockerfile me humne eng, hin, aur pan install kiya hai
OCR_LANG = "eng+hin+pan"
OCR_CONFIG = "--oem 3 --psm 6"

# ---------- IMAGE PREPROCESSING ----------
def preprocess_image(file_path):
    # OpenCV se image read karna
    img = cv2.imread(file_path)
    if img is None:
        return None
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Noise removal + Thresholding for better OCR
    gray = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    return thresh

def extract_from_image(file_path):
    processed = preprocess_image(file_path)
    if processed is None:
        return "Error: Could not process image"
        
    return pytesseract.image_to_string(
        processed,
        lang=OCR_LANG,
        config=OCR_CONFIG
    )

# ---------- PDF ----------
def extract_from_pdf(file_path):
    text = ""
    # 1. Pehle text-based PDF try karo (Fast & Accurate)
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception:
        pass

    # 2. Agar text nahi mila (Scanned PDF hai), toh OCR karo
    if not text.strip():
        # dpi=150 rakha hai taaki Render ki RAM (512MB) crash na ho
        images = convert_from_path(file_path, dpi=150)
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

# ---------- BACKGROUND TASK ----------
def process_file_async(file_path, ext, task_id):
    try:
        text = ""
        if ext in ["jpg", "jpeg", "png", "bmp", "gif", "webp"]:
            text = extract_from_image(file_path)
        elif ext == "pdf":
            text = extract_from_pdf(file_path)
        elif ext == "docx":
            text = extract_from_docx(file_path)
        else:
            text = "Unsupported file type"

        # Result ko text file me save karo
        result_path = os.path.join(UPLOAD_DIR, f"{task_id}.txt")
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(text)
            
    except Exception as e:
        with open(os.path.join(UPLOAD_DIR, f"{task_id}.txt"), "w", encoding="utf-8") as f:
            f.write(f"Error during processing: {str(e)}")
    finally:
        # Original file delete kar do space bachane ke liye (Optional)
        if os.path.exists(file_path):
            os.remove(file_path)

# ---------- API ENDPOINTS ----------

@app.post("/extract")
async def extract(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    task_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1].lower()
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    # File save karo
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # PDF or Heavy Image -> Background me dalo
    if ext == "pdf":
        background_tasks.add_task(process_file_async, file_path, ext, task_id)
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "File is being processed in background"
        }

    # Choti files -> Direct result
    try:
        if ext in ["jpg", "jpeg", "png", "bmp", "gif", "webp"]:
            text = extract_from_image(file_path)
        elif ext == "docx":
            text = extract_from_docx(file_path)
        else:
            return JSONResponse({"error": "Unsupported format"}, status_code=400)

        return {
            "filename": file.filename,
            "status": "completed",
            "extracted_text": text.strip()
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/result/{task_id}")
def get_result(task_id: str):
    result_file = os.path.join(UPLOAD_DIR, f"{task_id}.txt")

    if not os.path.exists(result_file):
        return {"status": "processing"}

    with open(result_file, "r", encoding="utf-8") as f:
        data = f.read()

    return {
        "status": "completed",
        "text": data
    }
