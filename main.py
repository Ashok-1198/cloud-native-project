import os
import json
import io
import base64
from flask import Flask, redirect, request, render_template_string
from google.cloud import storage
from io import BytesIO
import google.generativeai as genai
from PIL import Image
import google.cloud.secretmanager as secretmanager  

app = Flask(__name__)

BUCKET_NAME = 'cnd-z23746774-bucket'
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

secret_name = "projects/642128673446/secrets/GEMINI_API_KEY/versions/latest"

def get_gemini_api_key():
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(name=secret_name)
    return response.payload.data.decode("UTF-8")

genai.configure(api_key=get_gemini_api_key())  
MODEL_NAME = "gemini-1.5-flash" 

@app.route('/')
def index():
    files = list_files()

    html_template = """
    <html>
    <head>
        <title>Image Captioning App</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: blue;
                padding: 30px;
                color: #333;
            }
            .container {
                max-width: 700px;
                margin: 0 auto;
                background: #ffffff;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
            }
            h1 {
                color: #005cbf;
                text-align: center;
            }
            form {
                margin-bottom: 30px;
                text-align: center;
            }
            input[type="file"] {
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #ccc;
            }
            button {
                padding: 10px 20px;
                background-color: #005cbf;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                margin-top: 10px;
            }
            ul {
                list-style: none;
                padding: 0;
            }
            li {
                margin: 10px 0;
            }
            a {
                color: #005cbf;
                text-decoration: none;
                font-weight: bold;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Upload Image</h1>
            <form method="post" enctype="multipart/form-data" action="/upload">
                <input type="file" name="form_file" accept="image/jpeg" required/>
                <br>
                <button type="submit">Submit</button>
            </form>
            <h2>Uploaded Images</h2>
            <ul>
                {% for file in files %}
                    <li><a href="/files/{{ file }}">{{ file }}</a></li>
                {% endfor %}
            </ul>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template, files=files)

def upload_blob(file, destination_blob_name):
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file)
    return f"gs://{BUCKET_NAME}/{destination_blob_name}"

def generate_image_caption(image_data):
    try:
        image = Image.open(io.BytesIO(image_data))  
        model = genai.GenerativeModel(MODEL_NAME)

        prompt = """
        Analyze this image and generate:
        1. A short and catchy title for the image.
        2. A detailed description of what is happening in the image.

        Format the response as:
        Title: <short title here>
        Description: <detailed description here>
        """

        response = model.generate_content([prompt, image], stream=False)

        if not response or not hasattr(response, "parts") or not response.parts:
            return {"title": "Error", "description": "Gemini AI returned an empty response"}

        response_text = response.parts[0].text.strip()
        title = "Unknown"
        description = "No description available"

        for line in response_text.split("\n"):
            if line.lower().startswith("title:"):
                title = line.split("Title:", 1)[1].strip()
            elif line.lower().startswith("description:"):
                description = line.split("Description:", 1)[1].strip()

        return {"title": title, "description": description}

    except Exception as e:
        return {"title": "Error", "description": f"Could not generate caption: {e}"}

def save_json_metadata(filename, metadata):
    json_blob_name = filename.replace(".jpeg", ".json").replace(".jpg", ".json")
    blob = bucket.blob(json_blob_name)
    blob.upload_from_string(json.dumps(metadata), content_type="application/json")

@app.route('/upload', methods=["POST"])
def upload():
    file = request.files['form_file']
    filename = file.filename
    file.seek(0)  
    upload_blob(file, filename)
    file.seek(0) 
    image_data = file.read()
    metadata = generate_image_caption(image_data)  
    save_json_metadata(filename, metadata)
    return redirect("/")

def list_files():
    blobs = bucket.list_blobs()
    return [blob.name for blob in blobs if blob.name.lower().endswith(('.jpeg', '.jpg'))]

@app.route('/files/<filename>')
def get_file(filename):
    blob = bucket.blob(filename)
    image_data = blob.download_as_bytes()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    image_src = f"data:image/jpeg;base64,{image_base64}"

    metadata_blob_name = filename.replace(".jpeg", ".json").replace(".jpg", ".json")
    metadata_blob = bucket.blob(metadata_blob_name)

    title = "No Title Found"
    description = "No Description Available"
    if metadata_blob.exists():
        metadata_json = json.loads(metadata_blob.download_as_text())
        title = metadata_json.get("title", title)
        description = metadata_json.get("description", description)

    html_content = f"""
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: blue;
                padding: 30px;
                color: #333;
            }}
            .container {{
                max-width: 700px;
                margin: 0 auto;
                background: #ffffff;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
                text-align: center;
            }}
            h2 {{
                color: #005cbf;
            }}
            img {{
                max-width: 100%;
                border-radius: 10px;
                margin-top: 15px;
            }}
            p {{
                font-size: 1.1em;
                margin-top: 20px;
            }}
            a {{
                display: inline-block;
                margin-top: 20px;
                text-decoration: none;
                color: #005cbf;
                font-weight: bold;
            }}
            a:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>{title}</h2>
            <img src="{image_src}" alt="Uploaded Image"/>
            <p>{description}</p>
            <a href="/">← Back to Home</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
