import os
import json
import time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
import shutil

# Local Imports
import database as db
import auth
from auth import get_current_user_id

# Selenium & AI Imports
import openai
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import PyPDF2
import docx
import io

# INIT DB
db.init_db()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SETTINGS_FILE = "settings.json"
UPLOADS_DIR = "uploads"
COMET_BINARY = "/Applications/Comet.app/Contents/MacOS/Comet"

if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

# --------------------------
# STATE
# --------------------------
class GlobalState:
    def __init__(self):
        self.api_key: str = ""
        self.resume_text: str = ""
        self.driver: Optional[webdriver.Chrome] = None
        self.client: Optional[openai.OpenAI] = None
        self.uploaded_files: Dict[str, str] = {}
        self.chat_history: List[Dict[str, str]] = []
        self.load_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    self.api_key = data.get("api_key", "")
                    if self.api_key:
                        self.client = openai.OpenAI(api_key=self.api_key)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self, api_key: str):
        self.api_key = api_key
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump({"api_key": self.api_key}, f)
            self.client = openai.OpenAI(api_key=self.api_key)
        except Exception as e:
            print(f"Error saving settings: {e}")

state = GlobalState()

# --------------------------
# MODELS
# --------------------------

class ConnectRequest(BaseModel):
    mode: str
    browser_type: str = "chrome"
    url: Optional[str] = None
    debugger_port: Optional[int] = 9222

class ChatMessage(BaseModel):
    role: str
    content: str
class FillRequest(BaseModel):
    message: str 
    history: List[ChatMessage] = [] 

class SettingsRequest(BaseModel):
    api_key: str

class UserSignup(BaseModel):
    email: str
    password: str

class ExperienceData(BaseModel):
    title: str
    company: str
    start_date: str
    end_date: str
    description: str

class EducationData(BaseModel):
    school: str
    degree: str
    year: str

class ProfileData(BaseModel):
    full_name: str
    linkedin: Optional[str]
    website: Optional[str]
    phone: Optional[str]
    bio: Optional[str]
    skills: List[str] = []
    experiences: List[ExperienceData] = []
    educations: List[EducationData] = []

# --------------------------
# AUTH ENDPOINTS
# --------------------------

@app.post("/api/auth/signup")
def signup(user: UserSignup, db_sess: Session = Depends(db.get_db)):
    existing = db_sess.query(db.User).filter(db.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pw = auth.get_password_hash(user.password)
    new_user = db.User(email=user.email, password_hash=hashed_pw)
    db_sess.add(new_user)
    db_sess.commit()
    return {"message": "User created"}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db_sess: Session = Depends(db.get_db)):
    user = db_sess.query(db.User).filter(db.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    token = auth.create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

# --------------------------
# PROFILE ENDPOINTS
# --------------------------

@app.get("/api/profile")
def get_profile(user_id: int = Depends(get_current_user_id), db_sess: Session = Depends(db.get_db)):
    user = db_sess.query(db.User).filter(db.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    
    profile = user.profile
    
    data = {
        "full_name": profile.full_name if profile else "",
        "linkedin": profile.linkedin if profile else "",
        "website": profile.website if profile else "",
        "phone": profile.phone if profile else "",
        "bio": profile.bio if profile else "",
        "skills": [s.name for s in user.skills],
        "experiences": [
            {
                "title": e.title, "company": e.company, 
                "start_date": e.start_date, "end_date": e.end_date, 
                "description": e.description
            } for e in user.experiences
        ],
        "educations": [
            {"school": e.school, "degree": e.degree, "year": e.year} for e in user.educations
        ]
    }
    return data

@app.post("/api/profile")
def update_profile(data: ProfileData, user_id: int = Depends(get_current_user_id), db_sess: Session = Depends(db.get_db)):
    user = db_sess.query(db.User).filter(db.User.id == user_id).first()
    
    # Update Basic Info
    if not user.profile:
        user.profile = db.Profile(user_id=user_id)
        db_sess.add(user.profile)
    
    user.profile.full_name = data.full_name
    user.profile.linkedin = data.linkedin
    user.profile.website = data.website
    user.profile.phone = data.phone
    user.profile.bio = data.bio
    
    # Update Nested Lists (Clear & Re-Add Strategy for simplicity)
    db_sess.query(db.Skill).filter(db.Skill.user_id == user_id).delete()
    db_sess.query(db.Experience).filter(db.Experience.user_id == user_id).delete()
    db_sess.query(db.Education).filter(db.Education.user_id == user_id).delete()
    
    for s in data.skills:
        if s.strip():
            db_sess.add(db.Skill(user_id=user_id, name=s.strip()))
            
    for exp in data.experiences:
        db_sess.add(db.Experience(
            user_id=user_id, title=exp.title, company=exp.company,
            start_date=exp.start_date, end_date=exp.end_date, description=exp.description
        ))
        
    for edu in data.educations:
        db_sess.add(db.Education(
            user_id=user_id, school=edu.school, degree=edu.degree, year=edu.year
        ))

    db_sess.commit()
    return {"message": "Profile updated"}

# --------------------------
# APP LOGIC
# --------------------------

def get_openai_client():
    if not state.client:
        if not state.api_key:
             pass 
    return state.client

@app.get("/")
async def get_index():
    with open("templates/index.html", "r") as f:
        return HTMLResponse(f.read())

@app.get("/api/settings")
async def get_settings():
    return {"api_key": state.api_key}

@app.post("/api/settings")
async def update_settings_endpoint(req: SettingsRequest):
    state.save_settings(req.api_key)
    return {"status": "ok", "message": "Settings saved"}

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    combined_text = ""
    for file in files:
        if not file.filename: continue
        file_path = os.path.join(UPLOADS_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        state.uploaded_files[file.filename] = os.path.abspath(file_path)
        
        try:
            file.file.seek(0)
            content = file.file.read()
            filename = file.filename.lower()
            text = ""
            if filename.endswith('.pdf'):
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            elif filename.endswith('.docx'):
                doc = docx.Document(io.BytesIO(content))
                text = "\n".join([para.text for para in doc.paragraphs])
            else:
                text = content.decode("utf-8", errors="ignore")
            combined_text += f"\n--- START OF FILE: {file.filename} ---\n{text}\n--- END ---\n"
        except Exception as e:
            print(f"Error parsing {file.filename}: {e}")
            
    state.resume_text = combined_text
    return {"status": "ok", "message": f"Processed {len(files)} files."}

@app.post("/api/connect")
async def connect_browser(req: ConnectRequest):
    try:
        options = Options()
        if req.browser_type == "comet":
            if os.path.exists(COMET_BINARY):
                options.binary_location = COMET_BINARY
            else:
                raise HTTPException(status_code=400, detail="Comet binary not found.")
                
        # DRIVER INSTALLATION
        try:
            driver_path = ChromeDriverManager().install()
            print(f"Driver Path: {driver_path}")
            # Fix for common mac issue: sometimes path is not executable
            os.chmod(driver_path, 0o755)
            service = ChromeService(executable_path=driver_path)
        except Exception as e:
            print(f"Driver Install Failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to install driver: {e}")

        if req.mode == "existing":
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{req.debugger_port}")
            state.driver = webdriver.Chrome(service=service, options=options)
        else:
            options.add_argument("--start-maximized")
            options.add_experimental_option("detach", True)
            options.add_argument("--no-sandbox") 
            options.add_argument("--disable-dev-shm-usage")
            
            state.driver = webdriver.Chrome(service=service, options=options)
            if req.url: state.driver.get(req.url)
            
        return {"status": "ok", "message": f"{req.browser_type} connected"}
    except Exception as e:
        print(f"Error connecting browser: {e}")
        raise HTTPException(status_code=500, detail=f"Browser Error: {str(e)}")

@app.post("/api/fill")
async def perform_action(req: FillRequest, db_sess: Session = Depends(db.get_db), user_id: int = Depends(get_current_user_id)):
    if not state.driver:
        raise HTTPException(status_code=400, detail="Browser not connected")

    # Fetch User Profile Context
    profile_context = ""
    if user_id:
        user = db_sess.query(db.User).filter(db.User.id == user_id).first()
        if user and user.profile:
            p = user.profile
            skills = ", ".join([s.name for s in user.skills])
            
            experiences_str = ""
            for e in user.experiences:
                experiences_str += f"- {e.title} at {e.company} ({e.start_date} - {e.end_date}): {e.description}\n"
            
            educations_str = ""
            for e in user.educations:
                educations_str += f"- {e.degree} at {e.school} ({e.year})\n"
            
            profile_context = f"""
            SAVED USER PROFILE (HIGHEST PRIORITY):
            Name: {p.full_name}
            Phone: {p.phone}
            LinkedIn: {p.linkedin}
            Website: {p.website}
            Bio: {p.bio}
            
            SKILLS: {skills}
            
            EXPERIENCE:
            {experiences_str}
            
            EDUCATION:
            {educations_str}
            """

    try:
        # Scrape
        visible_elements = []
        tags = ["input", "textarea", "select", "button"]
        for tag in tags:
            els = state.driver.find_elements(By.TAG_NAME, tag)
            for el in els:
                try:
                    if el.is_displayed() and el.is_enabled():
                         if el.tag_name == "input" and el.get_attribute("type") == "hidden": continue
                         visible_elements.append(el)
                except: pass

        element_map = {}
        form_structure = []
        for idx, el in enumerate(visible_elements):
            key = f"el_{idx}"
            element_map[key] = el
            # Label
            label_text = ""
            try:
                if el.get_attribute("id"):
                    lbls = state.driver.find_elements(By.CSS_SELECTOR, f"label[for='{el.get_attribute('id')}']")
                    if lbls: label_text = lbls[0].text
                if not label_text:
                    if el.text: label_text = el.text
                    else:
                        p = el.find_element(By.XPATH, "..")
                        if p.tag_name in ["label", "button"]: label_text = p.text
            except: pass
            
            # Current Value & Placeholder
            current_val = ""
            placeholder = ""
            try:
                placeholder = el.get_attribute("placeholder")
                current_val = el.get_attribute("value")
                if not current_val and el.tag_name in ["textarea", "button", "select"]: 
                    current_val = el.text
            except: pass

            form_structure.append({
                "id": key,
                "tag": el.tag_name,
                "type": el.get_attribute("type"),
                "label": label_text[:60],
                "placeholder": str(placeholder)[:40],
                "current_val": str(current_val)[:50]
            })

        # AI
        client = get_openai_client()
        if hasattr(client, 'api_key') and not client.api_key:
             if state.api_key: client.api_key = state.api_key

        history_text = "\n".join([f"{m.role.upper()}: {m.content}" for m in req.history])
        
        prompt = f"""
        You are an intelligent Job Application Assistant.
        
        GOAL: Fill the job application form completely and accurately.
        
        RULES:
        1. **INCREMENTAL FILLING**: 
           - Check "current_val" in the Elements JSON.
           - If a field is ALREADY FILLED, DO NOT generate a 'fill' action.
           - FOCUS ON EMPTY FIELDS.
        
        2. **DATE FORMATTING (CRITICAL)**:
           - CHECK THE "placeholder" and "label" for format hints (e.g., "MM/DD/YYYY", "DD-MM-YYYY", "YYYY/MM/DD").
           - YOU MUST CONVERT the user's date to the EXACT format requested.
           - If split into 3 fields (Day, Month, Year), fill them individually.
        
        3. **SEARCH / DROPDOWNS**:
           - For "Location", "University", or "Company" search bars:
           - Fill the text and the system will press TAB to trigger search/validation.
           - If it is a native <select>, provide the exact visible text option.
        
        4. **IMPROVISE**: 
           - Search the Resume for answers not in the Profile. 
           - Infer professional answers if missing.

        {profile_context}
        
        UPLOADED RESUME (Secondary):
        {state.resume_text[:15000]}
        
        AVAILABLE FILES:
        {list(state.uploaded_files.keys())}
        
        CHAT HISTORY:
        {history_text}
        USER LATEST MESSAGE:
        {req.message}
        
        VISIBLE FORM ELEMENTS (JSON):
        {json.dumps(form_structure, indent=0)}
        
        TASK:
        Decide on the next set of actions.
        
        OUTPUT FORMAT (JSON):
        {{
            "actions": [
                {{"id": "el_0", "type": "fill", "value": "John"}},
                {{"id": "el_1", "type": "click"}}
            ],
            "missing_info": "Question to user if you absolutely cannot infer info"
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        ai_resp = json.loads(response.choices[0].message.content)
        actions = ai_resp.get("actions", [])
        missing_info = ai_resp.get("missing_info", None)
        user_msg = ai_resp.get("message_to_user", "Processed.")
        
        # Execute
        logs = []
        for action in actions:
            el_id = action.get("id")
            act_type = action.get("type")
            val = action.get("value")
            
            if el_id in element_map:
                el = element_map[el_id]
                try:
                    # Scroll & Focus
                    state.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.3) 
                    
                    if act_type == "fill":
                        if el.tag_name == "select":
                            try:
                                Select(el).select_by_visible_text(str(val))
                            except:
                                try:
                                    Select(el).select_by_value(str(val))
                                except:
                                    el.click()
                                    el.send_keys(str(val))
                                    el.send_keys(Keys.ENTER)
                        else:
                            # Robust text filling
                            el.clear()
                            el.send_keys(str(val))
                            time.sleep(0.1)
                            el.send_keys(Keys.TAB) # Trigger change/blur events
                            
                    elif act_type == "click":
                         el.click()
                         
                    elif act_type == "upload":
                        if val in state.uploaded_files:
                            el.send_keys(state.uploaded_files[val])
                            
                    logs.append(f"{act_type.capitalize()} on {el_id}")
                except Exception as e:
                    logs.append(f"Error {el_id}: {e}")
                    
        return {
            "status": "success",
            "reply": missing_info if missing_info else user_msg,
            "actions_taken": len(actions),
            "logs": logs
        }

    except Exception as e:
        return {"status": "error", "reply": f"Error: {str(e)}", "logs": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
