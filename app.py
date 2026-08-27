from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask import render_template_string
from functools import wraps
from google import genai
from google.genai import types
import requests
import re
import markdown
import json
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import time
import random
import urllib.parse
# import base64
# from google import generativeai as genai
# from google.generativeai import types
# Load environment variables
load_dotenv()


def _is_embeddable(video_id):
    """Return True if the video exists and can be embedded on other sites.
    Uses YouTube's public oEmbed endpoint (no API key required)."""
    try:
        oembed = ("https://www.youtube.com/oembed?url="
                  f"https://www.youtube.com/watch?v={video_id}&format=json")
        return requests.get(oembed, timeout=8).status_code == 200
    except Exception:
        return False


def get_youtube_urls_from_gemini_api(topics):
    """Find one real, embeddable YouTube video per topic.

    Searches YouTube directly and picks the first search result that is actually
    embeddable, so every topic gets a playable video (no AI guessing, no API key).
    Returns a list of [video_id] (empty string if nothing suitable was found),
    which the module template embeds as an iframe.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    results = []
    for topic in topics:
        video_id = ""
        try:
            query = urllib.parse.quote_plus(f"{topic} tutorial")
            search_url = f"https://www.youtube.com/results?search_query={query}"
            html = requests.get(search_url, headers=headers, timeout=15).text
            # Candidate video IDs in the order YouTube returned them (most relevant first)
            candidates = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            # De-duplicate while preserving order
            seen = set()
            candidates = [c for c in candidates if not (c in seen or seen.add(c))]
            # Pick the first result that is embeddable (check a few, then give up)
            for cand in candidates[:5]:
                if _is_embeddable(cand):
                    video_id = cand
                    break
            # If none verified as embeddable, fall back to the top result anyway
            if not video_id and candidates:
                video_id = candidates[0]
            print(f"Video for '{topic}': {video_id or 'NONE'}")
        except Exception as e:
            print(f"Error finding YouTube video for '{topic}': {e}")
        results.append([video_id])
    return results


# Global variables
global entry1, entry2, entry3, entry4, entry5, entry6, entry7
global txt1, link1, txt2, link2, txt3, link3, txt4, link4, txt5, link5, txt6, link6
entry1 = 0
entry2 = 0
entry3 = 0
entry4 = 0
entry5 = 0
entry6 = 0

modules_dict = {}
app = Flask(__name__)


def require_modules(f):
    """Redirect to home if no learning path has been generated yet,
    instead of crashing with an IndexError on an empty modules_dict."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not modules_dict:
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper


# Set up the new Generative AI client
# Read from environment / .env file
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
model_name = "gemini-flash-latest"  # Preferred model
# If the preferred model is overloaded (503), fall back to these (in order).
# They are usually available even when the newest model is swamped.
FALLBACK_MODELS = ["gemini-flash-lite-latest", "gemini-3.5-flash"]


def gemini_api_response(user_input, retries_per_model=2):
    """Generate content using the new Google GenAI library.

    Resilient to the free tier being flaky in two ways:
      1. Retries each model on transient errors (e.g. HTTP 503 "overloaded").
      2. Falls back to alternative models if the preferred one stays overloaded.
    Returns an error string only if every model fails.
    """
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=user_input),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=4000
    )

    transient = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                 "500", "INTERNAL", "overloaded", "high demand")
    last_error = None
    for model in [model_name] + FALLBACK_MODELS:
        for attempt in range(retries_per_model):
            try:
                response = gemini_client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                )
                return response.text
            except Exception as e:
                last_error = e
                msg = str(e)
                is_transient = any(code in msg for code in transient)
                # Retry the same model once more on a transient error...
                if is_transient and attempt < retries_per_model - 1:
                    time.sleep(min(2 ** attempt, 4))  # 1s, 2s
                    continue
                # ...otherwise move on to the next fallback model.
                print(f"Model '{model}' failed (attempt {attempt + 1}): {msg[:90]}")
                break
    print(f"All models failed: {last_error}")
    quota_exhausted = last_error and any(
        code in str(last_error) for code in ("429", "RESOURCE_EXHAUSTED"))
    if quota_exhausted:
        return "Daily limit reached — please try again tomorrow."
    return "Sorry, I encountered an error while generating the response."


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("About.html")


@app.route("/contact")
def contact():
    return render_template("Contact.html")


def classify_prompt(prompt):
    """
    Classifies a given prompt as either a 'topic' or a 'question'.
    """
    prompt = str(prompt)
    print(prompt)
    prompt = prompt.strip()
    if re.search(r'\b(what|how|why|when|where|who|which|can|is|are|does|did|should|could|would|explain|define|solve|find|calculate)\b', prompt, re.IGNORECASE):
        return "question"
    elif prompt.endswith('?'):
        return "question"
    return "topic"


def generate_learning_path(search_query):
    global modules_dict

    ip = f"""Create a structured learning path for {search_query} with exactly 6 modules. Format your response EXACTLY like this:

**Module 1: [Module Name]**
1. [Subtopic 1]
2. [Subtopic 2] 
3. [Subtopic 3]
4. [Subtopic 4]
5. [Subtopic 5]

**Module 2: [Module Name]**
1. [Subtopic 1]
2. [Subtopic 2]
3. [Subtopic 3] 
4. [Subtopic 4]
5. [Subtopic 5]

Continue this pattern for all 6 modules. Start with basics and progress to advanced topics. Only provide module names and subtopics, no additional text."""

    response_text = gemini_api_response(ip) or ""
    print("Raw response:")
    print(response_text)

    # Initialize the dictionary to store modules and their subtopics
    modules_dict.clear()

    # Split the content into modules using the **Module pattern
    # Skip the first empty element
    modules = response_text.split('**Module')[1:]
    print("++++++MODULES++++++")
    print(f"Found {len(modules)} modules")

    for i, module in enumerate(modules):
        print(f"++++++PROCESSING MODULE {i+1}++++++")
        print(f"Module content: {module[:200]}...")  # Show first 200 chars

        # Extract the module name and subtopics
        lines = module.strip().split('\n')

        # Get module name (first line, remove the trailing **)
        module_name_line = lines[0].strip()
        if '**' in module_name_line:
            module_name = module_name_line.replace('**', '').strip()
            # Remove any numbering from module name
            module_name = re.sub(r'^\d+:\s*', '', module_name).strip()
        else:
            continue  # Skip if we can't find a proper module name

        print(f"Module name: {module_name}")

        # Find subtopics (lines that start with numbers)
        subtopics = []
        for line in lines[1:]:
            line_stripped = line.strip()

            # Look for numbered items (1., 2., etc.)
            if re.match(r'^\d+\.', line_stripped):
                # Remove the number and clean up
                clean_line = re.sub(r'^\d+\.\s*', '', line_stripped).strip()
                if clean_line and clean_line not in subtopics:
                    subtopics.append(clean_line)

                if len(subtopics) >= 5:  # Limit to 5 subtopics
                    break

        print(f"Subtopics found: {subtopics}")
        print(f"Number of subtopics: {len(subtopics)}")

        # Add module and subtopics to the dictionary if we have both
        # At least 3 subtopics to be valid
        if module_name and len(subtopics) >= 3:
            modules_dict[f"Module {i+1}: {module_name}"] = subtopics
            print(f"Added to dictionary: Module {i+1}: {module_name}")
        else:
            print(f"Skipped module due to insufficient data")

    print("++++++FINAL MODULES DICT++++++")
    print(modules_dict)

    # If parsing failed, try alternative parsing method
    if not modules_dict:
        print("Primary parsing failed, trying alternative method...")
        modules_dict = alternative_parse_method(response_text)

    # If we still have nothing, the AI call likely failed (e.g. the model was
    # overloaded). Show a clear message instead of a blank/"stuck" page.
    if not modules_dict:
        return render_template_string("""
        <div style="font-family: Poppins, sans-serif; max-width: 640px; margin: 12vh auto;
                    text-align: center; color: #eee; background: #12203a; padding: 40px;
                    border-radius: 16px;">
            <h2>⚠️ Couldn't build your learning path just now</h2>
            <p style="line-height:1.6; color:#c9d4e6;">
                The AI service was busy or temporarily unavailable. This is usually
                temporary — please go back and try again in a few moments.
            </p>
            <a href="/" style="display:inline-block; margin-top:18px; padding:12px 26px;
               background:linear-gradient(135deg,#ff6a00,#ffb400); color:#111;
               text-decoration:none; border-radius:30px; font-weight:600;">
               ← Try again
            </a>
        </div>
        """), 503

    return render_template("result.html", modules=modules_dict)


def alternative_parse_method(response_text):
    """Alternative parsing method for different response formats"""
    alt_modules_dict = {}

    # Look for patterns like "1. Python Basics" followed by subtopics
    lines = response_text.split('\n')
    current_module = None
    current_subtopics = []
    module_counter = 1

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this is a main module (numbered item without indentation)
        if re.match(r'^\d+\.\s+[A-Z]', line) and not line.startswith('    '):
            # Save previous module if exists
            if current_module and current_subtopics:
                alt_modules_dict[f"Module {module_counter}: {current_module}"] = current_subtopics[:5]
                module_counter += 1

            # Start new module
            current_module = re.sub(r'^\d+\.\s*', '', line).strip()
            current_subtopics = []

        # Check if this is a subtopic (starts with * or is indented)
        elif line.startswith('*') or line.startswith('    *') or line.startswith('-'):
            subtopic = re.sub(r'^[\s\*\-]+', '', line).strip()
            if subtopic and len(current_subtopics) < 5:
                current_subtopics.append(subtopic)

    # Don't forget the last module
    if current_module and current_subtopics:
        alt_modules_dict[f"Module {module_counter}: {current_module}"] = current_subtopics[:5]

    print("Alternative parsing result:")
    print(alt_modules_dict)
    return alt_modules_dict
# def generate_learning_path(search_query):
#     global modules_dict

#     ip = f"Remember, tell me exactly what I ask. Don't give me any additional information. Give me exactly 6 main topics for {search_query}. The 6 main topics should be divided into modules, with the 1st module covering the basics and introduction. The topics should become more advanced as we progress to the next modules. Remember, under each module, you should give me exactly 5 subtopics for that particular module. The response you provide must be structured: first, list all 6 modules, then list all the subtopics. Remember, just give me the names of the topics and subtopics, and don't provide any additional information."

#     response_text = gemini_api_response(ip)
#     print(response_text)
#     # Initialize the dictionary to store modules and their subtopics
#     modules_dict.clear()

#     # Split the content into modules and subtopics
#     modules = response_text.split('**Module')
#     print("++++++MODULES++++++")
#     print(modules)
#     for module in modules[1:]:
#         # Extract the module name and subtopics
#         module_lines = module.strip().split('\n')
#         print("++++++MODULE LINES ++++++")
#         print(module_lines)
#         module_name = module_lines[0].strip()  # Get module name
#         print("++++++MODULE NAMES++++++")
#         print(module_name)
#         # Find the subtopics by extracting lines starting with a number
#         subtopics = []
#         for line in module_lines[1:]:
#             line_stripped = line.strip()
#             if line_stripped and (line_stripped[0].isdigit() or line_stripped.startswith('1.')):
#                 # Remove numbering and clean up
#                 clean_line = re.sub(r'^\d+\.?\s*', '', line_stripped)
#                 if clean_line:
#                     subtopics.append(clean_line)
#                 if len(subtopics) >= 5:  # Limit to 5 subtopics
#                     break
#         print("++++++SUBTOPICS ++++++")
#         print(subtopics)
#         # Add module and subtopics to the dictionary
#         if module_name and subtopics:
#             modules_dict[module_name] = subtopics

#     # Clean up any malformed keys
#     keys_to_remove = [key for key in modules_dict.keys() if len(key) < 5]
#     for key in keys_to_remove:
#         del modules_dict[key]
#     print(modules_dict)
#     return render_template("results3.html", modules=modules_dict)


def get_youtube_urls_with_ai(topics, api_key=None, max_results=1):
    """
    Use Gemini AI to find relevant YouTube video IDs for any topic
    This leverages AI's knowledge of popular educational videos
    """
    results = []

    for topic in topics:
        try:
            prompt = f"""Find the most popular and educational YouTube video for the topic: "{topic}"
            
            Respond with ONLY a YouTube video ID (the 11-character string after 'v=' in YouTube URLs).
            Choose videos that are:
            - Educational and tutorial-focused
            - From reputable channels
            - Suitable for learning
            
            If you don't know a specific video ID, respond with: "dQw4w9WgXcQ"
            
            Topic: {topic}
            Video ID:"""

            response = gemini_api_response(prompt)
            video_id = response.strip() if response else ""

            # Validate video ID format (11 characters, alphanumeric + _ -)
            if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                embed_url = f"https://www.youtube.com/embed/{video_id}"
                results.append([embed_url])
                print(f"AI found video for '{topic}': {video_id}")
            else:
                embed_url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
                results.append([embed_url])
                print(
                    f"AI couldn't find specific video for '{topic}', using fallback")

        except Exception as e:
            print(f"Error getting AI recommendation for '{topic}': {e}")
            embed_url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
            results.append([embed_url])

    return results
# Solution 2: Combination of search methods with better retry logic


def get_youtube_urls(topics, api_key=None, max_results=1):
    """
    Robust method that tries multiple approaches and has better rate limiting
    """
    results = []

    # Session for connection pooling
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    for i, topic in enumerate(topics):
        video_found = False

        # Method 1: Try Bing search (less restrictive than Google/DDG)
        try:
            if not video_found:
                delay = random.uniform(1, 3)
                time.sleep(delay)

                query = f"site:youtube.com {topic} tutorial"
                bing_url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}"

                response = session.get(bing_url, timeout=10)
                if response.status_code == 200:
                    # Extract YouTube URLs from Bing results
                    youtube_pattern = r'https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'
                    video_ids = re.findall(youtube_pattern, response.text)

                    if video_ids:
                        video_id = video_ids[0]  # Take first result
                        embed_url = f"https://www.youtube.com/embed/{video_id}"
                        results.append([embed_url])
                        print(f"Bing found video for '{topic}': {video_id}")
                        video_found = True
        except:
            pass

        # Method 2: Try StartPage search (Google proxy)
        try:
            if not video_found:
                delay = random.uniform(1, 3)
                time.sleep(delay)

                query = f"site:youtube.com {topic} tutorial"
                startpage_url = f"https://www.startpage.com/sp/search?query={urllib.parse.quote_plus(query)}"

                response = session.get(startpage_url, timeout=10)
                if response.status_code == 200:
                    youtube_pattern = r'https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'
                    video_ids = re.findall(youtube_pattern, response.text)

                    if video_ids:
                        video_id = video_ids[0]
                        embed_url = f"https://www.youtube.com/embed/{video_id}"
                        results.append([embed_url])
                        print(
                            f"StartPage found video for '{topic}': {video_id}")
                        video_found = True
        except:
            pass

        # Method 3: Use AI as fallback
        try:
            if not video_found:
                ai_result = get_youtube_urls_with_ai([topic], max_results=1)
                results.extend(ai_result)
                print(f"Used AI fallback for '{topic}'")
                video_found = True
        except:
            pass

        # Final fallback
        if not video_found:
            results.append(["https://www.youtube.com/embed/dQw4w9WgXcQ"])
            print(f"All methods failed for '{topic}', using default fallback")

    return results


def generate_module_content(module_topics):
    """Generate content for module topics using the new API"""
    content = []
    for topic in module_topics:
        prompt = f"Remember, tell me exactly what I ask. Don't give me any additional information. Give me exactly 300 words detailed paragraph about {topic}"
        response = gemini_api_response(prompt)
        content.append(response)
    return content


@app.route("/1")
@require_modules
def module_1():
    global entry1, txt1, link1

    if entry1 == 0:
        txt1 = generate_module_content(
            modules_dict[list(modules_dict.keys())[0]])
        link1 = get_youtube_urls_from_gemini_api(
            modules_dict[list(modules_dict.keys())[0]])
        entry1 = 1
        current_module_data = modules_dict[list(modules_dict.keys())[0]]
        return render_template("modules/module1.html", modules=modules_dict, module=current_module_data, text=txt1, links=link1)
    else:
        return render_template("modules/module1.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[0]],
                               text=txt1, links=link1)


@app.route("/2")
@require_modules
def module_2():
    global entry2, txt2, link2

    if entry2 == 0:
        txt2 = generate_module_content(
            modules_dict[list(modules_dict.keys())[1]])
        link2 = get_youtube_urls_from_gemini_api(
            modules_dict[list(modules_dict.keys())[1]])
        entry2 = 1
        return render_template("modules/module2.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[1]],
                               text=txt2, links=link2)
    else:
        return render_template("modules/module2.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[1]],
                               text=txt2, links=link2)


@app.route("/3")
@require_modules
def module_3():
    global entry3, txt3, link3

    if entry3 == 0:
        txt3 = generate_module_content(
            modules_dict[list(modules_dict.keys())[2]])
        link3 = get_youtube_urls_from_gemini_api(
            modules_dict[list(modules_dict.keys())[2]])
        entry3 = 1
        return render_template("modules/module3.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[2]],
                               text=txt3, links=link3)
    else:
        return render_template("modules/module3.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[2]],
                               text=txt3, links=link3)


@app.route("/4")
@require_modules
def module_4():
    global entry4, txt4, link4

    if entry4 == 0:
        txt4 = generate_module_content(
            modules_dict[list(modules_dict.keys())[3]])
        link4 = get_youtube_urls_from_gemini_api(
            modules_dict[list(modules_dict.keys())[3]])
        entry4 = 1
        return render_template("modules/module4.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[3]],
                               text=txt4, links=link4)
    else:
        return render_template("modules/module4.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[3]],
                               text=txt4, links=link4)


@app.route("/5")
@require_modules
def module_5():
    global entry5, txt5, link5

    if entry5 == 0:
        txt5 = generate_module_content(
            modules_dict[list(modules_dict.keys())[4]])
        link5 = get_youtube_urls_from_gemini_api(
            modules_dict[list(modules_dict.keys())[4]])
        entry5 = 1
        return render_template("modules/module5.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[4]],
                               text=txt5, links=link5)
    else:
        return render_template("modules/module5.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[4]],
                               text=txt5, links=link5)


@app.route("/6")
@require_modules
def module_6():
    global entry6, txt6, link6

    if entry6 == 0:
        txt6 = generate_module_content(
            modules_dict[list(modules_dict.keys())[5]])
        link6 = get_youtube_urls_from_gemini_api(
            modules_dict[list(modules_dict.keys())[5]])
        entry6 = 1
        return render_template("modules/module6.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[5]],
                               text=txt6, links=link6)
    else:
        return render_template("modules/module6.html", modules=modules_dict,
                               module=modules_dict[list(
                                   modules_dict.keys())[5]],
                               text=txt6, links=link6)


def generate_prompt(user_input, input_type):
    """
    Generates a prompt based on input type (topic or question) and returns rendered HTML.
    """
    if input_type == "topic":
        return generate_learning_path(user_input)
    elif input_type == "question":
        prompt = (f"Act as a knowledgeable tutor. Answer the following question: '{user_input}'"
                  "Please break down your answer into distinct, easy-to-follow steps. Each step should be in its own block for clarity. The structure should be:"
                  "1. **Step 1: Restate the Problem** "
                  "Start by restating the question in your own words. Clarify any important details to ensure the question is well understood."
                  "2. **Step 2: Identify Key Concepts** "
                  "Outline the key concepts or principles that are necessary to answer this question. If applicable, provide any formulas, theories, or foundational ideas."
                  "3. **Step 3: Approach the Solution**  "
                  "Walk through the process or methodology needed to solve the problem. Be as clear as possible, breaking down each action in logical order."
                  "4. **Step 4: Apply the Concepts** "
                  'Demonstrate how to apply the key concepts to the problem at hand. Use examples, numbers, or explanations to show how the theory is applied.'
                  " 5. **Step 5: Summarize the Solution** "
                  "Recap the solution, including key takeaways and any final thoughts. If there are any additional points or caveats, mention them here."
                  "'Ensure each step is clear and easy to follow. Use formatting or bullet points for additional clarity. Avoid using overly technical language unless it necessary for the explanation.")

        response_text = gemini_api_response(prompt)
        if response_text:
            response_text = markdown.markdown(response_text)
        return render_template("response.html", response_text=response_text)
    else:
        # Handle invalid input type
        return render_template("result.html", response_text="Invalid input type. Please provide either 'topic' or 'question'.")


@app.route("/generate", methods=["POST"])
def process_input():
    """
    Processes user input, classifies it as a topic or question,
    and generates a prompt accordingly.
    """
    modules_dict.clear()
    user_input = request.form.get("search_query")  # User's input from the form
    input_type = classify_prompt(user_input)    # Classify as topic or question
    # Generate appropriate prompt
    return generate_prompt(user_input, input_type)


def render_quiz_template(quiz_q, quiz_a=None, user_answers=None, score=None):
    """Render the quiz form. When quiz_a/user_answers are provided, renders the
    graded view instead: options are disabled, the correct answer is highlighted
    green, and the student's wrong pick (if any) is highlighted red."""
    graded = quiz_a is not None and user_answers is not None
    quiz_html = ""
    for i, (question, options) in enumerate(quiz_q.items()):
        quiz_html += f"<div class='quiz-question'><p>{i+1}. {question}</p>"
        for option in options:
            css_class = ""
            if graded:
                if option == quiz_a[i]:
                    css_class = "quiz-correct"
                elif option == user_answers.get(f"question-{i}"):
                    css_class = "quiz-wrong"
            checked = "checked" if graded and user_answers.get(
                f"question-{i}") == option else ""
            disabled = "disabled" if graded else ""
            quiz_html += (f'<label class="{css_class}"><input type="radio" name="question-{i}" '
                          f'value="{option}" {checked} {disabled}> {option}</label><br>')
        quiz_html += "</div>"

    style = """
    <style>
        .quiz-question { margin-bottom: 16px; }
        .quiz-question p { font-weight: 600; margin-bottom: 8px; }
        .quiz-question label { display: block; padding: 6px 10px; border-radius: 6px; margin-bottom: 4px; }
        .quiz-correct { background: rgba(76, 175, 80, 0.25); color: #4caf50; font-weight: 600; }
        .quiz-wrong { background: rgba(244, 67, 54, 0.25); color: #f44336; font-weight: 600; }
        .quiz-score { font-size: 1.2rem; font-weight: 700; margin-top: 12px; }
    </style>
    """

    if graded:
        return f"""
        {style}
        {quiz_html}
        <p class="quiz-score">Your score: {score}/{len(quiz_q)}</p>
        """

    return f"""
    {style}
    <form id="quizForm">
        {quiz_html}
        <button type="button" onclick="submitQuizForm()">Submit</button>
    </form>
    """


# Caches the generated quiz (questions + answer key) per module route, so the
# answers submitted are graded against the same quiz the student was shown.
quiz_cache = {}


def generate_quiz(module_index, route_name):
    """Generate (GET) or grade (POST) the quiz for a specific module."""
    if request.method == 'POST':
        cached = quiz_cache.get(route_name)
        if not cached:
            return render_template_string("<p>Your quiz session expired. Please reopen the quiz.</p>")
        quiz_q, quiz_a = cached["quiz_q"], cached["quiz_a"]
        user_answers = request.form
        score = sum(1 for i in range(len(quiz_q))
                    if user_answers.get(f"question-{i}") == quiz_a[i])
        return render_template_string(render_quiz_template(quiz_q, quiz_a, user_answers, score))

    try:
        prompt = f"do exactly what i say don't do any thing extra give me a quiz on topics{str(modules_dict[list(modules_dict.keys())[module_index]])} it should have exactly 5 questions remember exactly 5 questions and 4 options for each and hear me this is the main part all questions and options you give me must be in the form of a dictionary named as quiz_q all the questions must be the keys and options must be in the form of lists and correct answers must be returned separately in a list named as quiz_a"

        response_text = gemini_api_response(prompt)
        # Ensure response_text is a string before calling replace
        if response_text is None:
            response_text = ""
        else:
            response_text = str(response_text).replace(
                "\n", " ").replace("     ", "")

        # Parse the response to extract quiz_q and quiz_a
        if "quiz_q = " in response_text and "quiz_a = " in response_text:
            response_text1 = response_text.split("quiz_q = ")[1]
            dic = response_text1.split("quiz_a = ")
            quiz_q = eval(dic[0])
            quiz_a = eval(dic[1].replace("```", ""))
        else:
            # Fallback: create a simple quiz if parsing fails
            quiz_q = {"What is the main topic of this module?": [
                "Option A", "Option B", "Option C", "Option D"]}
            quiz_a = ["Option A"]

    except Exception as e:
        print(f"Error generating quiz: {e}")
        # Fallback: create a simple quiz
        quiz_q = {"Sample question about the module topics?": [
            "Option A", "Option B", "Option C", "Option D"]}
        quiz_a = ["Option A"]

    quiz_cache[route_name] = {"quiz_q": quiz_q, "quiz_a": quiz_a}
    return render_template_string(render_quiz_template(quiz_q))


@app.route("/q1", methods=['GET', 'POST'])
def quiz_module1():
    return generate_quiz(0, "q1")


@app.route("/q2", methods=['GET', 'POST'])
def quiz_module2():
    return generate_quiz(1, "q2")


@app.route("/q3", methods=['GET', 'POST'])
def quiz_module3():
    return generate_quiz(2, "q3")


@app.route("/q4", methods=['GET', 'POST'])
def quiz_module4():
    return generate_quiz(3, "q4")


@app.route("/q5", methods=['GET', 'POST'])
def quiz_module5():
    return generate_quiz(4, "q5")


@app.route("/q6", methods=['GET', 'POST'])
def quiz_module6():
    return generate_quiz(5, "q6")


@app.route("/c")
def index():
    return render_template("chat.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")
    if not user_message.strip():
        return jsonify({"error": "Empty message!"}), 400

    # Call the new Gemini API
    bot_response = gemini_api_response(user_message)
    if bot_response:
        bot_response = markdown.markdown(
            bot_response, extensions=['fenced_code', 'tables', 'toc'])
    return jsonify({"response": bot_response})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
