from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil, os, uuid, pytesseract, pdfplumber, cv2, re
import numpy as np
from pdf2image import convert_from_path
from docx import Document

app = FastAPI()

# ---------- CORS Fix (Sab jagah se access allow) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Render ka Temp Storage (RAM-based Disk)
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# English Only Core Configuration
OCR_CONFIG = "--oem 3 --psm 3"
LANG = "eng"

def get_processed_image(img_array):
    """Heavy Image Preprocessing for Max Accuracy"""
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    
    # Resize: 1.5x (Accuracy badhata hai without crashing server)
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LANCZOS4)
    
    # Sharpness & Noise Removal
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Adaptive Thresholding (Low light images ke liye best)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 21, 10
    )
    
    return thresh

def clean_text(text):
    """Output se kachra hatane ke liye"""
    text = re.sub(r'[|\\_~^]', '', text) # Faltu symbols delete
    text = re.sub(r' +', ' ', text)      # Extra spaces fix
    return text.strip()

def extract_from_image(file_path):
    img = cv2.imread(file_path)
    if img is None: return "Error: Image not readable"
    processed = get_processed_image(img)
    raw_text = pytesseract.image_to_string(processed, lang=LANG, config=OCR_CONFIG)
    return clean_text(raw_text)

def extract_from_pdf(file_path):
    text = ""
    # 1. Digital PDF (Direct Text) - Fast & Accurate
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
    except: pass

    # 2. Scanned PDF (OCR) - Heavy Processing
    if not text.strip():
        # DPI 150 (Safe for 512MB RAM, but clear enough for OCR)
        images = convert_from_path(file_path, dpi=150)
        for img in images:
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            processed = get_processed_image(img_cv)
            raw_text = pytesseract.image_to_string(processed, lang=LANG, config=OCR_CONFIG)
            text += clean_text(raw_text) + "\n"
    return text

# ---------- BACKGROUND TASK ENGINE ----------
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

        # Result save in /tmp
        result_path = os.path.join(UPLOAD_DIR, f"{task_id}.txt")
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        with open(os.path.join(UPLOAD_DIR, f"{task_id}.txt"), "w", encoding="utf-8") as f:
            f.write(f"Error: {str(e)}")
    finally:
        # Original file delete to save space
        if os.path.exists(file_path): os.remove(file_path)

# ---------- API ENDPOINTS ----------

@app.post("/extract")
async def extract(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    task_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1].lower()
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Everything goes to background task for stability
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
