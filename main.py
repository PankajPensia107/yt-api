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

# PSM 3: Automatic page segmentation (Better for paragraphs/bills)
OCR_CONFIG = "--oem 3 --psm 3"

# ---------- IMAGE PREPROCESSING (Advanced) ----------
def get_processed_image(img_array):
    # 1. Grayscale conversion
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)

    # 2. Resizing (Upscaling): Image ko 2 guna bada karna (Blurry text fix)
    # Tesseract ko bade letters zyada pasand hain
    height, width = gray.shape[:2]
    gray = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

    # 3. Denoising: Grains aur dots saaf karna
    # h=10: Filter strength (zyada badhane se text gayab ho sakta hai)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # 4. Adaptive Thresholding: Contrast badhana (Black text on White background)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 31, 2
    )

    return thresh

def extract_from_image(file_path, lang):
    img = cv2.imread(file_path)
    if img is None: return "Error: Image not readable"
    
    processed = get_processed_image(img)
    return pytesseract.image_to_string(processed, lang=lang, config=OCR_CONFIG)

# ---------- PDF ----------
def extract_from_pdf(file_path, lang):
    text = ""
    # Try direct text extraction
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
    except: pass

    # If Scanned PDF -> OCR with Preprocessing
    if not text.strip():
        # DPI 200: Clarity ke liye zaroori hai (RAM check)
        images = convert_from_path(file_path, dpi=200)
        for img in images:
            img_np = np.array(img)
            img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            processed = get_processed_image(img_cv)
            text += pytesseract.image_to_string(processed, lang=lang, config=OCR_CONFIG)
    return text

# ---------- BACKGROUND TASK ----------
def process_file_async(file_path, ext, task_id, lang):
    try:
        text = ""
        if ext in ["jpg", "jpeg", "png", "bmp", "webp"]:
            text = extract_from_image(file_path, lang)
        elif ext == "pdf":
            text = extract_from_pdf(file_path, lang)
        elif ext == "docx":
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        else:
            text = "Unsupported file type"

        # Cleaning: Faltu symbols hatane ke liye basic cleanup (Optional)
        # text = "".join([c for c in text if c.isalnum() or c in " \n.,-:@/"])

        result_path = os.path.join(UPLOAD_DIR, f"{task_id}.txt")
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(text.strip())

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
    lang: str = Form("eng"), # Default English
    background_tasks: BackgroundTasks = None
):
    task_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1].lower()
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    # Validating lang parameter
    valid_langs = ["eng", "hin", "pan", "eng+hin", "eng+pan", "eng+hin+pan"]
    if lang not in valid_langs:
        lang = "eng"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(process_file_async, file_path, ext, task_id, lang)
    
    return {"task_id": task_id, "status": "processing"}

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    result_file = os.path.join(UPLOAD_DIR, f"{task_id}.txt")
    
    if not os.path.exists(result_file):
        return {"status": "processing"}

    with open(result_file, "r", encoding="utf-8") as f:
        data = f.read()
    
    return {"status": "completed", "text": data}
