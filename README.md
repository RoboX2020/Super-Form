# 🚀 Super-Form - AI Form Filler

**Super-Form** is an intelligent, local-first agentic tool that uses AI to automatically fill out complex job application forms. It connects to your browser, reads the page, and fills in details from your saved profile and resume.

## ✨ Features
- **AI Auto-Fill**: Intelligently fills inputs, textareas, and dropdowns.
- **Smart Date & Search**: Handles date formats and search/location fields automatically.
- **Resume Parsing**: Extracts context from your uploaded PDF/DOCX resume.
- **Persistent Profile**: Save your Experience, Education, and Skills once.
- **Privacy First**: Runs locally on your machine. Your data stays with you.

## 🛠️ Installation

Since Super-Form controls your local browser for automation, it must be run locally (not in the cloud).

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/super-form.git
   cd super-form
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements_web.txt
   ```

3. **Run the Server**
   ```bash
   ./venv/bin/uvicorn server:app --reload
   ```

4. **Launch**
   Open [http://localhost:8000](http://localhost:8000) in your browser.

## 💡 Usage
1. **Sign Up/Login**: Create a local account.
2. **Setup Profile**: Go to "My Profile" and add your work history.
3. **Connect Browser**: Click "Connect Browser" -> "Launch New".
4. **Navigate**: Go to a job posting (e.g., LinkedIn, Workday).
5. **Start**: Type "Fill this form" in the Super-Form chat.

## 🔧 Technology
- **Backend**: Python (FastAPI)
- **Frontend**: HTML/JS (Single Page App)
- **Automation**: Selenium WebDriver
- **AI**: OpenAI GPT-4o-mini
