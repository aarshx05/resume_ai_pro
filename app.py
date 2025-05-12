import os
import json
import requests
import re
from flask import Flask, render_template, request, redirect, url_for
from pdfminer.high_level import extract_text
import docx2txt
import urllib.parse
from dotenv import load_dotenv
from itertools import cycle
from threading import Lock

# Flask app setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# OpenRouter API setup
#API_KEY = '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'
#API_KEY = os.getenv('OPENROUTER_API_KEY')

# List of API keys
API_KEYS = [
    os.getenv('API_KEY_1'),
    os.getenv('API_KEY_2'),
    os.getenv('API_KEY_3'),
    os.getenv('API_KEY_4'),
    os.getenv('API_KEY_5'),
    os.getenv('API_KEY_6'),
    os.getenv('API_KEY_7'),
    os.getenv('API_KEY_8'),
    os.getenv('API_KEY_9')
]

# Create a thread-safe cycle
api_key_cycle = cycle(API_KEYS)
key_lock = Lock()

def get_next_api_key():
    with key_lock:
        return next(api_key_cycle)
    
BASE_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Extract text from PDF or DOCX
def extract_resume_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text(file_path)
    elif ext == ".docx":
        return docx2txt.process(file_path)
    else:
        raise ValueError("Unsupported file type")

# Extract JSON safely from OpenRouter response
def extract_json_from_response(response_text):
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                return {"error": "Invalid JSON found in response"}
        return {"error": "No valid JSON structure found"}

# Call OpenRouter API with prompt
def parse_with_openrouter(text):
    headers = {
        "Authorization": f"Bearer {get_next_api_key()}",

        "Content-Type": "application/json",

        "X-Title": "ResumeParserApp"
    }
    
    prompt = f"""
You are an expert resume parser. From the resume text below, return a valid JSON object with these keys:

- "Basic Info" (Full Name, Email, Phone, Address)
- "About Me"
- "Skills"
- "Experience"
- "Education"
- "Projects"
- "Certifications"
- "Awards and Honors"
- "References"
- "Links" (like LinkedIn, GitHub)
- "Extracurricular Activities"
- "Volunteering Experience"
- "Hobbies & Interests"

Important:
- Use only the content in the resume as-is.
- Normalize and organize data neatly.

Mandatory:
- Respond with only valid JSON. No markdown or extra explanation.

Resume Text:
{text}
"""

    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        response = requests.post(BASE_URL, headers=headers, json=payload)
        print("API Response JSON:", response)
        if response.status_code == 200:
            raw_output = response.json()['choices'][0]['message']['content']

            print("API Response JSON:", raw_output)
            return extract_json_from_response(raw_output)
        else:
            print("API Error:", response.text)
            return {"error": "API returned an error."}
    except Exception as e:
        print("Exception:", e)
        return {"error": "API call failed."}


# Route to display home page (Landing page)
@app.route('/', methods=['GET'])
def index():
    return render_template('home.html')

# Route to handle resume uploading or updating
@app.route('/update', methods=['GET', 'POST'])
def update():
    if request.method == 'POST':
        resume_file = request.files['resume']
        if resume_file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_file.filename)
            resume_file.save(file_path)

            raw_text = extract_resume_text(file_path)
            parsed_data = parse_with_openrouter(raw_text)

            if isinstance(parsed_data, dict) and 'error' not in parsed_data:
                return render_template('result.html', data=parsed_data, file_path=file_path)
            else:
                return render_template('error.html', message=parsed_data.get('error', 'Failed to parse.'))

    # Check if there is existing parsed resume data in localStorage
    parsed_data = request.cookies.get('parsedResumeData')
    return render_template('upload.html', parsed_data=parsed_data)

# Route to display AI assistant page and generate cover letter
@app.route('/ai', methods=['GET'])
def ai_page():
    return render_template('ai_assistant.html')

@app.route('/result', methods=['POST'])
def result():
    parsed_data = request.form.get('parsed_resume_data')

    if parsed_data:
        try:
            # Decode the string from the form and parse it as JSON
            parsed_data = urllib.parse.unquote(parsed_data)
            parsed_data = json.loads(parsed_data)

            # Render the result page with the parsed data
            return render_template('result.html', data=parsed_data)
        except json.JSONDecodeError:
            return render_template('error.html', message="Failed to decode the parsed data.")
    else:
        return redirect('/update')
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}

    messages = data.get("messages", [])
    resume_data = data.get("resume_data", "")
    job_description = data.get("job_description", "")
    if job_description:
        job_description = job_description.strip()

    # Prepare headers for the OpenRouter API
    headers = {
      "Authorization": f"Bearer {get_next_api_key()}",

        "Content-Type": "application/json",
        
        "X-Title": "ResumeChatAssistant"
    }

    # Construct system prompt using resume and job description
    system_prompt = "You are an expert AI assistant. Use the following resume data to help the user with job applications and questions:\n\n"
    system_prompt += resume_data if resume_data else "No resume data provided."

    if job_description:
        system_prompt += f"\n\nJob Description:\n{job_description}"

    # Combine with chat history
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # Prepare payload for OpenRouter API
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": full_messages
    }

    # Send to OpenRouter API
    try:
        response = requests.post(BASE_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            reply = response.json()['choices'][0]['message']['content']
            return {"reply": reply}
        else:
            return {"reply": f"Failed with status {response.status_code}: {response.text}"}

    except Exception as e:
        return {"reply": "Error occurred: " + str(e)}

# Run the app
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
