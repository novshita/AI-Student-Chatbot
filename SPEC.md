# 📋 Project Specification — AI Chatbot for Personalised Student Assistance

> This document describes the **purpose, plan, and design** behind the project.
> For installation and usage instructions, see [README.md](README.md).

---

## 1. Overview

The AI Chatbot for Personalised Student Assistance is a Flask web application that acts as a
personal learning companion. A student provides an input — either a **topic** they want to learn
or a **question** they need answered — and the system uses Google's **Gemini AI** to respond in
the most useful format:

- A **topic** → a structured, multi-module **learning path** with content, videos, and quizzes.
- A **question** → a clear, **step-by-step tutored answer**.

The goal is to make self-directed learning easier by automatically organising knowledge into a
guided path rather than leaving students to search and structure everything themselves.

---

## 2. Problem Statement

Students learning a new subject online face three common problems:

1. **Where to start** — they don't know what order to learn topics in.
2. **Information overload** — search results are scattered and unstructured.
3. **No feedback** — there's no easy way to check whether they've actually understood a topic.

This project addresses all three by generating an ordered curriculum, summarising each topic, and
providing quizzes to test understanding.

---

## 3. Goals & Non-Goals

### Goals
- Accept free-form student input and automatically detect intent (topic vs. question).
- Generate a 6-module learning path with subtopics for any topic.
- Produce readable explanations for each subtopic.
- Recommend a relevant YouTube tutorial per subtopic.
- Generate short quizzes to test knowledge and score the student's answers.
- Provide a free-form AI chat mode for ad-hoc questions.

### Non-Goals (out of scope for this version)
- User accounts, authentication, or saved progress across sessions.
- A database — state is kept in memory for the duration of the server run.
- Mobile app or offline support.
- Verified accuracy of AI content (responses are AI-generated and not fact-checked).

---

## 4. Target Users

- **Primary:** Students / self-learners exploring a new subject who want a guided plan.
- **Secondary:** Anyone who wants quick, structured explanations or a study quiz on a topic.

---

## 5. Functional Requirements

### 5.1 Input Classification
- The system inspects the user's input and classifies it as a **question** or a **topic**.
- Rule: if the input contains question words (*what, how, why, when, where, who, which, can, is,
  are, does, did, should, could, would, explain, define, solve, find, calculate*) or ends with
  `?`, it is treated as a **question**; otherwise it is a **topic**.

### 5.2 Learning Path Generation (topic)
- Gemini is prompted to return **exactly 6 modules**, each with **5 subtopics**, ordered from
  basics to advanced.
- The response is parsed into a dictionary: `{ "Module N: Name": [subtopic1, ...] }`.
- A fallback parser handles differently-formatted AI responses.
- The parsed path is rendered on the results page.

### 5.3 Module Content (per module)
- For each subtopic in a module, Gemini generates a ~300-word explanatory paragraph.
- For each subtopic, a relevant **YouTube tutorial video** is found by searching YouTube
  directly (no AI): the app queries YouTube's search results, then verifies each candidate is
  actually embeddable (via YouTube's public oEmbed endpoint) and embeds the first valid one.
  This guarantees a real, playable video per subtopic and uses no Gemini quota.
- Content is generated on first visit and cached in memory so repeat visits are instant.

### 5.4 Question Answering (question)
- Gemini answers in a fixed 5-step tutor format:
  1. Restate the problem
  2. Identify key concepts
  3. Approach the solution
  4. Apply the concepts
  5. Summarise the solution
- The answer is converted from Markdown to HTML and displayed.

### 5.5 Quizzes
- For each module, Gemini generates **5 multiple-choice questions**, each with **4 options** and a
  separate list of correct answers.
- On submission, the app compares the student's answers and displays a score out of 5.
- A fallback quiz is shown if generation or parsing fails.

### 5.6 AI Chat
- A dedicated chat page sends user messages to Gemini and returns the response as JSON.

---

## 6. User Flow

```
          ┌─────────────┐
          │  Home page  │  user enters a topic or question
          └──────┬──────┘
                 │  POST /generate
                 ▼
        ┌──────────────────┐
        │ classify_prompt  │
        └───────┬──────────┘
        topic   │   question
     ┌──────────┘         └──────────┐
     ▼                               ▼
 Learning path (6 modules)     Step-by-step answer
     │                               (response page)
     ▼
 Module pages /1../6  ──►  Quizzes /q1../q6
 (content + videos)         (5 Q's, scored)
```

---

## 7. System Architecture

- **Framework:** Flask (single `app.py`), Jinja2 templates for the frontend.
- **AI layer:** `google-genai` SDK calling the Gemini API.
  - Text generation model: `gemini-flash-latest` (learning paths, module content, answers, quizzes, chat).
- **Video discovery:** direct YouTube search over HTTP (`requests`) + oEmbed embeddability check.
  No AI and no API key involved.
- **State:** in-memory Python globals.
  - `modules_dict` — the current learning path.
  - `entry1..6`, `txt1..6`, `link1..6` — cache flags and cached content per module.
- **Config:** `GEMINI_API_KEY` loaded from a `.env` file via `python-dotenv`.

### Component diagram
```
Browser ──HTTP──► Flask (app.py) ──► Gemini API (google-genai)
                     │                     └─ text generation
                     ├─ classify_prompt()        (intent detection)
                     ├─ generate_learning_path()  (topic → modules)
                     ├─ generate_module_content()  (subtopic → paragraph)
                     ├─ get_youtube_urls_from_gemini_api()  (subtopic → embedded video, via YouTube search)
                     ├─ generate_quiz()            (module → quiz + scoring)
                     └─ gemini_api_response()       (shared text call)
```

---

## 8. Route / API Specification

| Route          | Method   | Purpose                                            |
|----------------|----------|----------------------------------------------------|
| `/`            | GET      | Home page with the input form                      |
| `/generate`    | POST     | Classify input, return learning path or answer     |
| `/1` … `/6`    | GET      | Module pages (content + video links)               |
| `/q1` … `/q6`  | GET/POST | Quiz per module; POST submits answers for scoring  |
| `/c`           | GET      | AI chat page                                       |
| `/chat`        | POST     | Chat API — accepts `{message}`, returns `{response}`|
| `/about`       | GET      | About page                                         |
| `/contact`     | GET      | Contact page                                       |

The module routes are guarded: if no learning path has been generated yet, they redirect to the
home page instead of erroring.

---

## 9. Data Model

The core in-memory structure is `modules_dict`:

```python
{
  "Module 1: Introduction to X": ["Subtopic A", "Subtopic B", "Subtopic C", "Subtopic D", "Subtopic E"],
  "Module 2: ...":               [ ... ],
  ...
}
```

Per-module cached content:
- `txtN` — list of generated paragraphs (one per subtopic).
- `linkN` — list of YouTube video IDs (one per subtopic) used to embed the video.
- `entryN` — flag marking whether module N has already been generated.

---

## 10. Constraints & Assumptions

- **API key required** — the app cannot function without a valid `GEMINI_API_KEY`.
- **Free-tier quota** — Gemini's free tier limits daily requests. A full module page uses ~5
  requests (one per subtopic paragraph; videos no longer use Gemini), so heavy use can exhaust
  the daily allowance (resets at midnight Pacific Time).
- **In-memory state** — the learning path is lost when the server restarts, and is shared globally
  (not per-user), so the app is intended for single-user / demo use.
- **AI variability** — responses may vary in format; parsers include fallbacks but are not perfect.

---

## 11. Known Limitations

- No persistence — refreshing after a restart requires regenerating the learning path.
- Global state means concurrent users would share the same learning path.
- Video discovery reads YouTube's public search results page, which is not an official API;
  if YouTube changes that page's structure, the video feature may need a small update.
- Quiz parsing relies on the AI returning a specific structure.

---

## 12. Future Enhancements

- Persist learning paths and quiz scores in a database.
- Add user accounts and per-user progress tracking.
- Cache AI responses to reduce API usage and cost.
- Improve quiz generation robustness and explanation of correct answers.
- Deploy publicly (e.g. Render / PythonAnywhere) with a production WSGI server.

---

## 13. Tech Stack Summary

| Layer     | Technology                                   |
|-----------|----------------------------------------------|
| Backend   | Python, Flask                                |
| AI        | Google Gemini API (`google-genai` SDK)       |
| Frontend  | HTML, Jinja2 templates, CSS                  |
| Utilities | `markdown`, `requests`, `beautifulsoup4`, `python-dotenv` |
| Config    | `.env` file (API key)                        |
