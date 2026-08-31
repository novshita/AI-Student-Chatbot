# 🎓 AI Chatbot for Personalised Student Assistance

A web-based learning assistant powered by Google's **Gemini AI**. Students create an account,
enter any topic or question, and the app generates a **structured learning path**, **module
content**, **recommended YouTube tutorials**, and **auto-generated quizzes** — with an AI tutor
chat available right on every module page. Each account's learning path is saved and persists
across logins and devices.

---

## ✨ Features

- **User accounts** – sign up with email/password; your learning path, generated module content,
  and quiz cache persist across logins and devices instead of resetting.
- **Smart input detection** – automatically figures out whether you typed a *topic* or a *question*.
- **Learning paths** – enter a topic (e.g. *"Data Structures"*) and get a 6-module curriculum,
  each with 5 subtopics, ordered from basics to advanced.
- **Module pages** – each module generates detailed explanations plus a relevant, embedded
  YouTube tutorial video for every subtopic (found via YouTube search).
- **Step-by-step answers** – ask a question and get a clear, tutor-style breakdown (restate →
  key concepts → approach → apply → summary).
- **Auto-generated quizzes** – 5-question multiple-choice quizzes per module, graded in place with
  correct/incorrect answers highlighted (green/red) — no page reload needed.
- **AI chat widget** – expandable chat panel embedded directly on every module page, so you can
  ask questions without leaving your lesson.

---

## 📸 Screenshots


| Home page | Learning path |
|-----------|---------------|
| ![Home page](screenshots/home.png) | ![Learning path](screenshots/learning-path.png) |

| Module page | AI chat |
|-------------|---------|
| ![Module page](screenshots/module.png) | ![AI chat](screenshots/chat.png) |


---

## 🛠️ Tech Stack

- **Backend:** Python, [Flask](https://flask.palletsprojects.com/)
- **Auth & database:** `Flask-Login` (sessions/auth), `Flask-SQLAlchemy` + SQLite (accounts,
  saved learning paths)
- **AI:** [Google Gemini API](https://ai.google.dev/) via the `google-genai` SDK
- **Frontend:** HTML + Jinja2 templates, CSS
- **Other:** `markdown`, `requests`, `python-dotenv`

---

## 📁 Project Structure

```
Student_Chatbot/
├── app.py                # Main Flask application (routes, AI logic, auth, database models)
├── requirements.txt      # Python dependencies
├── .env.example          # Template for your API key + session secret (copy to .env)
├── .gitignore            # Keeps .env, .venv, and instance/ (local database) out of git
├── instance/
│   └── app.db            # SQLite database (accounts + saved learning paths) — auto-created,
│                          # not committed
├── static/
│   ├── style.css
│   └── astronaut.png
└── templates/
    ├── index.html         # Home page (enter a topic/question)
    ├── login.html         # Log in page
    ├── signup.html        # Sign up page
    ├── result.html        # Learning-path results
    ├── response.html      # Step-by-step answer to a question
    ├── _chat_widget.html  # AI chat panel, included on every module page
    ├── About.html
    ├── Contact.html
    └── modules/
        └── module1.html ... module6.html
```

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2. Create a virtual environment and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate          # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Add your Gemini API key
Get a free key from **[Google AI Studio](https://aistudio.google.com/app/apikey)**, then:
```bash
cp .env.example .env               # On Windows: copy .env.example .env
```
Open `.env` and paste your key:
```
GEMINI_API_KEY=your_key_here
```
Optionally also set `FLASK_SECRET_KEY` in `.env` to a random string — without it, a new key is
generated every time the server restarts, which logs everyone out (session cookies become invalid).

The SQLite database (`instance/app.db`) is created automatically on first run — no setup needed.

### 4. Run the app
```bash
python app.py
```
Open your browser at **http://127.0.0.1:5001**

---

## 🗺️ Routes

| Route            | Description                                  | Auth required |
|------------------|-----------------------------------------------|:---:|
| `/`              | Home page – enter a topic or question         | No |
| `/signup`        | Create an account (email + password)          | No |
| `/login`         | Log in                                        | No |
| `/logout`        | Log out                                       | Yes |
| `/generate`      | Processes input → learning path or answer     | Yes |
| `/1` … `/6`      | Module pages with content + video links       | Yes |
| `/q1` … `/q6`    | Quizzes for each module                       | Yes |
| `/chat`          | AI chat widget's API endpoint (POST)          | Yes |
| `/about`         | About page                                    | No |
| `/contact`       | Contact page                                  | No |

Routes marked "Auth required" redirect to `/login` if you're not signed in.

---

## ⚠️ Notes & Limitations

- **API key is required.** The app won't generate content without a valid `GEMINI_API_KEY`.
- **Free-tier quota.** Google's free tier limits how many requests you can make per day.
  Generating a module page's content uses one request per subtopic (usually 5), so heavy use
  can hit the daily limit — it resets automatically at midnight Pacific Time. When it does,
  you'll see a clear "Daily limit reached" message instead of a generic error.
- **Keep your key private.** Never commit your real `.env` file. It's already listed in
  `.gitignore`, so `git` will not upload it.
- **Login persistence depends on `FLASK_SECRET_KEY`.** Without a fixed value in `.env`, every
  server restart generates a new random key, which invalidates all existing login sessions.
- **One saved path per account.** Generating a new learning path while logged in overwrites
  your previously saved one — there's no history of multiple past paths yet.

---

## 📌 Future Improvements

- Persist chat history across page navigation (currently resets on refresh/module switch).
- Support multiple saved learning paths per account, with history instead of overwriting.
- Caching AI responses to reduce API usage.
- Password reset / email verification flow.

---

*Built as a learning project. Contributions and suggestions welcome!*
