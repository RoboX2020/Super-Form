const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');

let chatHistory = [];
let token = localStorage.getItem('token');

window.onload = function () {
    if (!token) {
        showView('auth');
    } else {
        showView('app');
        loadProfile();
        loadSettings();
    }
};

/* AUTH */
function showAuth(type) {
    document.getElementById('form-login').style.display = type === 'login' ? 'block' : 'none';
    document.getElementById('form-signup').style.display = type === 'signup' ? 'block' : 'none';
}

async function doLogin() {
    const email = document.getElementById('loginEmail').value;
    const pass = document.getElementById('loginPass').value;
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', pass);

    try {
        const res = await fetch('/api/auth/login', { method: 'POST', body: params });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Login failed');
        localStorage.setItem('token', data.access_token);
        token = data.access_token;
        showView('app');
        loadProfile();
        loadSettings();
    } catch (e) { alert("Login Failed: " + e.message); }
}

async function doSignup() {
    const email = document.getElementById('signupEmail').value;
    const pass = document.getElementById('signupPass').value;
    try {
        const res = await fetch('/api/auth/signup', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password: pass })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Signup failed');
        alert("Account Created! Please Login.");
        showAuth('login');
    } catch (e) { alert("Signup Failed: " + e.message); }
}

function doLogout() { localStorage.removeItem('token'); location.reload(); }
function showView(view) {
    document.getElementById('view-auth').style.display = view === 'auth' ? 'block' : 'none';
    document.getElementById('view-app').style.display = view === 'app' ? 'flex' : 'none';
}

/* NAV */
function showSection(section) {
    ['dashboard', 'profile', 'settings'].forEach(s => {
        document.getElementById(`section-${s}`).style.display = 'none';
        document.getElementById(`nav-${s}`).classList.remove('active');
    });
    document.getElementById(`section-${section}`).style.display = 'block';
    document.getElementById(`nav-${section}`).classList.add('active');
}

/* DYNAMIC PROFILE FORMS */
function addExperience(data = {}) {
    const div = document.createElement('div');
    div.className = 'list-item experience-item';
    div.innerHTML = `
        <span class="remove-btn" onclick="this.parentElement.remove()">Remove</span>
        <div class="row">
            <div class="col"><label>Title</label><input type="text" class="exp-title" value="${data.title || ''}"></div>
            <div class="col"><label>Company</label><input type="text" class="exp-company" value="${data.company || ''}"></div>
        </div>
        <div class="row">
            <div class="col"><label>Start Date</label><input type="text" class="exp-start" value="${data.start_date || ''}" placeholder="e.g. Jan 2020"></div>
            <div class="col"><label>End Date</label><input type="text" class="exp-end" value="${data.end_date || ''}" placeholder="Present"></div>
        </div>
        <label>Description</label>
        <textarea class="exp-desc" placeholder="Details...">${data.description || ''}</textarea>
    `;
    document.getElementById('experienceList').appendChild(div);
}

function addEducation(data = {}) {
    const div = document.createElement('div');
    div.className = 'list-item education-item';
    div.innerHTML = `
        <span class="remove-btn" onclick="this.parentElement.remove()">Remove</span>
        <div class="row">
            <div class="col"><label>School/University</label><input type="text" class="edu-school" value="${data.school || ''}"></div>
            <div class="col"><label>Degree</label><input type="text" class="edu-degree" value="${data.degree || ''}"></div>
            <div class="col" style="flex: 0.5;"><label>Year</label><input type="text" class="edu-year" value="${data.year || ''}"></div>
        </div>
    `;
    document.getElementById('educationList').appendChild(div);
}

async function loadProfile() {
    try {
        const res = await fetch('/api/profile', { headers: { 'Authorization': `Bearer ${token}` } });
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('profName').value = data.full_name || '';
        document.getElementById('profLinkedin').value = data.linkedin || '';
        document.getElementById('profPhone').value = data.phone || '';
        document.getElementById('profWebsite').value = data.website || '';
        document.getElementById('profBio').value = data.bio || '';
        document.getElementById('profSkills').value = (data.skills || []).join(', ');

        const expList = document.getElementById('experienceList');
        expList.innerHTML = '';
        (data.experiences || []).forEach(e => addExperience(e));

        const eduList = document.getElementById('educationList');
        eduList.innerHTML = '';
        (data.educations || []).forEach(e => addEducation(e));

    } catch (e) { console.log("Profile Load Error", e); }
}

async function saveProfile() {
    const experiences = [];
    document.querySelectorAll('.experience-item').forEach(el => {
        experiences.push({
            title: el.querySelector('.exp-title').value,
            company: el.querySelector('.exp-company').value,
            start_date: el.querySelector('.exp-start').value,
            end_date: el.querySelector('.exp-end').value,
            description: el.querySelector('.exp-desc').value
        });
    });

    const educations = [];
    document.querySelectorAll('.education-item').forEach(el => {
        educations.push({
            school: el.querySelector('.edu-school').value,
            degree: el.querySelector('.edu-degree').value,
            year: el.querySelector('.edu-year').value
        });
    });

    const skillsStr = document.getElementById('profSkills').value;
    const skills = skillsStr.split(',').map(s => s.trim()).filter(s => s);

    const payload = {
        full_name: document.getElementById('profName').value,
        linkedin: document.getElementById('profLinkedin').value,
        phone: document.getElementById('profPhone').value,
        website: document.getElementById('profWebsite').value,
        bio: document.getElementById('profBio').value,
        experiences: experiences,
        educations: educations,
        skills: skills
    };

    try {
        const res = await fetch('/api/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast('✅ Profile saved successfully!', 'success');
        } else {
            showToast('❌ Failed to save profile', 'error');
        }
    } catch (e) {
        showToast('❌ Error saving profile', 'error');
    }
}

/* TOAST NOTIFICATION */
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/* CHAT */
function handleEnter(e) { if (e.key === 'Enter') sendMessage(); }
function sendStart() {
    document.getElementById('chatInput').value = "Start filling.";
    sendMessage();
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;

    addMessage('user', msg);
    input.value = '';
    chatHistory.push({ role: 'user', content: msg });
    addMessage('bot', 'Thinking...');

    try {
        const res = await fetch('/api/fill', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ message: msg, history: chatHistory })
        });

        // Remove thinking message
        const thinkingMsg = document.querySelector('.chat-message.bot:last-child');
        if (thinkingMsg) thinkingMsg.remove();

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            const errorMsg = errorData.detail || `Server error (${res.status})`;
            addMessage('bot', `Error: ${errorMsg}`);
            return;
        }

        const data = await res.json();
        let reply;

        if (data.status === 'success') {
            reply = data.reply || `Done! Executed ${data.actions_taken || 0} actions.`;
        } else {
            reply = `Error: ${data.reply || data.detail || 'Unknown error occurred'}`;
        }

        addMessage('bot', reply);
        chatHistory.push({ role: 'assistant', content: reply });

    } catch (e) {
        const thinkingMsg = document.querySelector('.chat-message.bot:last-child');
        if (thinkingMsg) thinkingMsg.remove();
        addMessage('bot', `Network Error: ${e.message}`);
    }
}

function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    div.textContent = text;
    document.getElementById('chatContainer').appendChild(div);
    document.getElementById('chatContainer').scrollTop = document.getElementById('chatContainer').scrollHeight;
}

/* SETTINGS & FILES */
async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        if (data.api_key) document.getElementById('settingApiKey').value = data.api_key;
    } catch (e) { }
}

async function saveSettings() {
    const key = document.getElementById('settingApiKey').value;
    await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key: key }) });
    showToast('✅ Settings saved!', 'success');
}

if (dropZone) {
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('dragover'); });
    dropZone.addEventListener('drop', (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFiles(e.dataTransfer.files); });
    fileInput.addEventListener('change', (e) => { handleFiles(e.target.files); });
}

async function handleFiles(files) {
    if (files.length === 0) return;
    const formData = new FormData();
    for (const file of files) formData.append('files', file);
    addMessage('user', `Uploading ${files.length} file(s)...`);
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        addMessage('bot', `Uploaded: ${data.message}`);
    } catch (e) { addMessage('bot', "Upload Error"); }
}

/* CONNECT MODAL */
function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    document.getElementById(`tab-${tab}`).style.display = 'block';
}

async function connectBrowser(mode) {
    const url = document.getElementById('startUrl').value;
    const browserType = document.getElementById('browserType').value;
    closeModal('connectModal');
    addMessage('bot', `Connecting to ${browserType}...`);
    try {
        const res = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode, url, browser_type: browserType })
        });
        const data = await res.json();
        if (res.ok) {
            addMessage('bot', "Browser Connected! 🟢");
            document.querySelector('.indicator').classList.remove('disconnected');
            document.querySelector('.indicator').classList.add('connected');
            document.querySelector('.status-card span').textContent = 'Connected';
        } else {
            addMessage('bot', `Connection Failed: ${data.detail}`);
        }
    } catch (e) { addMessage('bot', `Error: ${e.message}`); }
}
