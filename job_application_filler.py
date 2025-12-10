import sys
import threading
import json
import time
import os
from typing import Optional, Dict, List

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFileDialog, QGroupBox, QMessageBox)
from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot

# --------------------------
# DEPENDENCIES
# --------------------------
try:
    import openai
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.remote.webelement import WebElement
    import PyPDF2
    import docx
except ImportError as e:
    print(f"Missing dependencies: {e}")

# --------------------------
# CONFIGURATION
# --------------------------

# ENTER YOUR OPENAI API KEY HERE IF YOU DO NOT WISH TO ENTER IT EVERY TIME
# ENTER YOUR OPENAI API KEY HERE IF YOU DO NOT WISH TO ENTER IT EVERY TIME
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --------------------------
# LOGIC CLASS
# --------------------------

class WorkerSignals(QObject):
    log = pyqtSignal(str)
    finished_launch = pyqtSignal() # Signal when browser launch is done
    finished_fill = pyqtSignal()   # Signal when fill is done
    error = pyqtSignal(str)

class JobFillerAI:
    def __init__(self, api_key: str, resume_path: str, signals: WorkerSignals):
        self.api_key = api_key
        self.resume_path = resume_path
        self.signals = signals
        self.resume_text = ""
        self.driver = None
        # Configure OpenAI
        self.client = openai.OpenAI(api_key=self.api_key)

    def log(self, msg):
        self.signals.log.emit(msg)

    def load_resume(self):
        self.log(f"Loading resume from {self.resume_path}...")
        try:
            if self.resume_path.lower().endswith('.pdf'):
                with open(self.resume_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    self.resume_text = text
            elif self.resume_path.lower().endswith('.docx'):
                doc = docx.Document(self.resume_path)
                self.resume_text = "\n".join([para.text for para in doc.paragraphs])
            else:
                # Assume text
                with open(self.resume_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.resume_text = f.read()
            
            self.log(f"Resume loaded. Length: {len(self.resume_text)} chars.")
        except Exception as e:
            self.log(f"Error loading resume: {e}")
            raise e

    def start_browser(self, url: str):
        self.log("Starting Browser...")
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_experimental_option("detach", True) 
            
            self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
            self.log(f"Navigating to {url}...")
            self.driver.get(url)
            self.log("Browser Ready. Use 'Fill Visible Page' when ready.")
        except Exception as e:
            self.log(f"Error starting browser: {e}")
            raise e

    def extract_form_elements(self) -> List[WebElement]:
        self.log("Scanning page for form fields...")
        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
        selects = self.driver.find_elements(By.TAG_NAME, "select")
        
        visible_elements = []
        for el in inputs + textareas + selects:
            try:
                if el.is_displayed() and el.is_enabled():
                    if el.get_attribute("type") not in ['submit', 'button', 'hidden', 'image', 'reset']:
                        visible_elements.append(el)
            except:
                pass
        
        self.log(f"Found {len(visible_elements)} visible fillable elements.")
        return visible_elements

    def get_element_identifiers(self, element: WebElement) -> dict:
        return {
            "tag": element.tag_name,
            "type": element.get_attribute("type"),
            "id": element.get_attribute("id"),
            "name": element.get_attribute("name"),
            "placeholder": element.get_attribute("placeholder"),
            "label": self.find_label(element)
        }

    def find_label(self, element: WebElement) -> str:
        try:
            id_attr = element.get_attribute("id")
            if id_attr:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{id_attr}']")
                if labels:
                    return labels[0].text
            parent = element.find_element(By.XPATH, "..")
            if parent.tag_name == "label":
                return parent.text
        except:
            pass
        return ""

    def analyze_and_fill(self, user_instructions: str):
        if not self.driver:
            self.log("Browser not started.")
            return

        elements = self.extract_form_elements()
        if not elements:
            self.log("No fields found to fill.")
            return

        form_structure = []
        element_map = {} 

        for idx, el in enumerate(elements):
            details = self.get_element_identifiers(el)
            key = f"field_{idx}"
            element_map[key] = el
            form_structure.append({
                "id": key,
                "details": details
            })

        self.log("Sending data to OpenAI for analysis...")
        
        prompt = f"""
        You are a helpful assistant filling out a job application.
        
        USER RESUME/INFO:
        {self.resume_text[:10000]} 

        USER INSTRUCTIONS:
        {user_instructions}
        
        JOB FORM FIELDS (JSON):
        {json.dumps(form_structure, indent=0)}

        INSTRUCTIONS:
        - Analyze the user's resume, instructions, and the form fields.
        - content: The value to fill in the field.
        - For radio/checkbox, return "true" (checked) or "false".
        - For Select (dropdown), return the value or exact text to select.
        
        Return ONLY a JSON object mapping 'id' to 'value'.
        Example: {{"field_0": "John", "field_1": "Doe"}}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": "You are a precise data entry assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            fill_data = json.loads(content)
            
            self.log("Received AI response. Filling fields...")

            for field_id, value in fill_data.items():
                if field_id in element_map and value:
                    el = element_map[field_id]
                    try:
                        self.log(f"Filling {field_id} with: {value}")
                        tag_name = el.tag_name
                        input_type = el.get_attribute("type")

                        if tag_name == "select":
                            select = Select(el)
                            try:
                                select.select_by_visible_text(value)
                            except:
                                try:
                                    select.select_by_value(value)
                                except:
                                    self.log(f"Could not select {value} in select box.")
                        elif input_type in ['checkbox', 'radio']:
                            is_checked = el.is_selected()
                            should_check = str(value).lower() in ['true', 'yes', '1', 'checked']
                            if should_check and not is_checked:
                                el.click()
                            elif not should_check and is_checked and input_type == 'checkbox':
                                el.click() # Uncheck
                        else:
                            el.clear()
                            el.send_keys(str(value))
                    except Exception as e:
                        self.log(f"Error filling {field_id}: {e}")

            self.log("Done filling fields.")

        except Exception as e:
            self.log(f"Error calling OpenAI or parsing: {e}")

# --------------------------
# GUI CLASS (PyQt6)
# --------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Job Application Filler")
        self.resize(700, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # API Key
        group_api = QGroupBox("Settings")
        layout_api = QHBoxLayout()
        self.api_key_input = QLineEdit(DEFAULT_API_KEY)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout_api.addWidget(QLabel("OpenAI API Key:"))
        layout_api.addWidget(self.api_key_input)
        group_api.setLayout(layout_api)
        layout.addWidget(group_api)
        
        # Resume
        group_resume = QGroupBox("Resume")
        layout_resume = QHBoxLayout()
        self.resume_path_input = QLineEdit()
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.clicked.connect(self.browse_resume)
        layout_resume.addWidget(self.resume_path_input)
        layout_resume.addWidget(self.btn_browse)
        group_resume.setLayout(layout_resume)
        layout.addWidget(group_resume)
        
        # URL
        group_url = QGroupBox("Job Application URL")
        layout_url = QHBoxLayout()
        self.url_input = QLineEdit()
        layout_url.addWidget(self.url_input)
        group_url.setLayout(layout_url)
        layout.addWidget(group_url)
        
        # Step 1: Launch
        self.btn_launch = QPushButton("1. Launch Browser")
        self.btn_launch.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        self.btn_launch.clicked.connect(self.launch_browser_thread)
        layout.addWidget(self.btn_launch)

        # Instructions
        group_instr = QGroupBox("Additional Instructions (Optional)")
        layout_instr = QVBoxLayout()
        self.instructions_input = QTextEdit()
        self.instructions_input.setPlaceholderText("E.g., 'Put 50000 for expected salary', 'Mention I love coding', 'Use my secondary address'")
        self.instructions_input.setMaximumHeight(80)
        layout_instr.addWidget(self.instructions_input)
        group_instr.setLayout(layout_instr)
        layout.addWidget(group_instr)

        # Step 2: Fill
        self.btn_fill = QPushButton("2. Fill Visible Page")
        self.btn_fill.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.btn_fill.clicked.connect(self.fill_page_thread)
        self.btn_fill.setEnabled(False) # Disabled until browser launched
        layout.addWidget(self.btn_fill)
        
        # Logger
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        # State
        self.bot = None

    def browse_resume(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Resume", "", "All Files (*);;PDF Files (*.pdf);;Word Files (*.docx)")
        if fname:
            self.resume_path_input.setText(fname)

    def log(self, message):
        self.log_area.append(message)

    def launch_browser_thread(self):
        api = self.api_key_input.text()
        resume = self.resume_path_input.text()
        url = self.url_input.text()

        if not api or not resume or not url:
            QMessageBox.critical(self, "Error", "Please fill all fields (API Key, Resume, URL)")
            return

        self.btn_launch.setEnabled(False)
        self.log("Initializing...")

        self.worker_signals = WorkerSignals()
        self.worker_signals.log.connect(self.log)
        self.worker_signals.finished_launch.connect(self.on_launch_finished)
        
        self.bot = JobFillerAI(api, resume, self.worker_signals)
        
        t = threading.Thread(target=self._launch_target, args=(url,))
        t.start()

    def _launch_target(self, url):
        try:
            self.bot.load_resume()
            self.bot.start_browser(url)
        except Exception as e:
            self.worker_signals.log.emit(f"Launch failed: {str(e)}")
        finally:
            self.worker_signals.finished_launch.emit()

    def on_launch_finished(self):
        self.btn_fill.setEnabled(True)
        self.log("Browser Launched. Log in or navigate to the form, then click 'Fill Visible Page'.")

    def fill_page_thread(self):
        if not self.bot:
            return
        
        instructions = self.instructions_input.toPlainText()
        self.btn_fill.setEnabled(False)
        
        self.worker_signals.finished_fill.connect(self.on_fill_finished)
        t = threading.Thread(target=self._fill_target, args=(instructions,))
        t.start()

    def _fill_target(self, instructions):
        try:
            self.bot.analyze_and_fill(instructions)
        except Exception as e:
            self.worker_signals.log.emit(f"Fill failed: {str(e)}")
        finally:
            self.worker_signals.finished_fill.emit()

    def on_fill_finished(self):
        self.btn_fill.setEnabled(True)
        # We don't disconnect signals here strictly, but usually good practice. 
        # For this simple app, it's fine.

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
