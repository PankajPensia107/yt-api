from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil, os, uuid, pytesseract, pdfplumber, cv2, re
import numpy as np
from pdf2image import convert_from_path
from docx import Document

app = FastAPI()

# CORS Fix
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# English Only Configuration
# PSM 3: Automatic page segmentation (Standard for documents)
# OEM 3: Default OCR Engine mode
OCR_CONFIG = "--oem 3 --psm 6"
LANG = "eng+hin" # Sirf English rakha hai abhi

def get_processed_image(img_array):
    # 1. Grayscale
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)

    # 2. Resizing (1.5x for clarity without crashing Render RAM)
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LANCZOS4)

    # 3. Denoising: Bilateral filter edges (letters) ko sharp rakhta hai
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # 4. Binary Thresholding: Pure Black & White (Otsu method)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Morphological Cleaning: Chote dots aur noise hatane ke liye
    kernel = np.ones((1,1), np.uint8)
    processed = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    return processed

def clean_text(text):
    """Faltu symbols aur extra spaces hatane ke liye post-processing"""
    # 1. Faltu symbols like |, _, ~, ^, etc. ko delete karo
    text = re.sub(r'[|\\_~^]', '', text)
    # 2. Extra spaces aur newlines ko manage karo
    text = re.sub(r' +', ' ', text)
    # 3. Double words ko single karo (Optional, but helps with blurring errors)
    # text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    return text.strip()

def extract_from_image(file_path):
    img = cv2.imread(file_path)
    if img is None: return "Error: Image not readable"
    
    processed = get_processed_image(img)
    raw_text = pytesseract.image_to_string(processed, lang=LANG, config=OCR_CONFIG)
    
    return clean_text(raw_text)

def extract_from_pdf(file_path):
    text = ""
    # Text-based PDF extraction
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
    except: pass

    # Scanned PDF logic
    if not text.strip():
        images = convert_from_path(file_path, dpi=200)
        for img in images:
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            processed = get_processed_image(img_cv)
            raw_text = pytesseract.image_to_string(processed, lang=LANG, config=OCR_CONFIG)
            text += clean_text(raw_text) + "\n"
    return text

# ---------- BACKGROUND TASK ----------
def process_file_async(file_path, ext, task_id):
    try:
        if ext in ["jpg", "jpeg", "png", "bmp", "webp"]:
            text = extract_from_image(file_path)
        elif ext == "pdf":
            text = extract_from_pdf(file_path)
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
        if os.path.exists(file_path): os.remove(file_path)

# ---------- API ENDPOINTS ----------

@app.post("/extract")
async def extract(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    task_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1].lower()
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(process_file_async, file_path, ext, task_id)
    
    return {"task_id": task_id, "status": "processing"}

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    result_file = os.path.join(UPLOAD_DIR, f"{task_id}.txt")
    if not os.path.exists(result_file):
        return {"status": "processing"}

    with open(result_file, "r", encoding="utf-8") as f:
        data = f.read()
    
    return {"status": "completed", "text": data}
