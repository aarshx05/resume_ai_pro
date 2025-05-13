import os
import json
import re
from flask import Flask, render_template, request, redirect, url_for
from pdfminer.high_level import extract_text
import docx2txt
from dotenv import load_dotenv
import urllib.parse

from dotenv import load_dotenv

from together import Together



# Flask app setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


TOGETHER_API_KEY = 'ab87d52c4444d33fdd260271f2a61920828f63a2315d906b893a202ce1bd5a2e'  # Replace with your actual key
client = Together(api_key=TOGETHER_API_KEY)

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
- Respond ONLY with valid JSON. No markdown or explanation.

Resume Text:
{text}
"""
    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        content = response.choices[0].message.content
        return extract_json_from_response(content)
    except Exception as e:
        return {"error": str(e)}



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


    system_prompt = "You are an expert AI assistant. Use the following resume data to help the user with job applications and questions (Answer In A Good Format):\n\n"

    system_prompt += resume_data if resume_data else "No resume data provided."

    if job_description:
        system_prompt += f"\n\nJob Description:\n{job_description}"

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=full_messages,
            stream=False
        )
        reply = response.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"Error occurred: {str(e)}"}


# Run the app
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
