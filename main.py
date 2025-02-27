import os
import json
import io
from flask import Flask, redirect, request, send_file
from google.cloud import storage
from io import BytesIO
import google.generativeai as genai
from PIL import Image
import google.cloud.secretmanager as secretmanager  

app = Flask(__name__)

# Set up Google Cloud Storage bucket
BUCKET_NAME = 'cnd-z23746774-bucket'
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)




secret_name = "projects/642128673446/secrets/GEMINI_API_KEY/versions/latest"



def get_gemini_api_key():
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(name=secret_name)
    return response.payload.data.decode("UTF-8")

# Configure Gemini AI API
genai.configure(api_key=get_gemini_api_key())  
MODEL_NAME = "gemini-1.5-flash" 

@app.route('/')
def index():
    index_html = """
    <form method="post" enctype="multipart/form-data" action="/upload">
        <div>
            <label for="file">Choose file to upload</label>
            <input type="file" id="file" name="form_file" accept="image/jpeg"/>
        </div>
        <div>
            <button>Submit</button>
        </div>
    </form>
    <ul>
    """
    
    for file in list_files():
        index_html += f'<li><a href="/files/{file}">{file}</a></li>'
    
    index_html += "</ul>"
    return index_html


def upload_blob(file, destination_blob_name):
    """Uploads a file to the Google Cloud Storage bucket."""
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file)
    return f"gs://{BUCKET_NAME}/{destination_blob_name}"


def generate_image_caption(image_data):
    """Uses Gemini AI to generate a title and description separately."""
    try:
        image = Image.open(io.BytesIO(image_data))  # Convert bytes to PIL Image
        model = genai.GenerativeModel(MODEL_NAME)

        # FIX: Improved Prompt for Separate Title & Description
        prompt = """
        Analyze this image and generate:
        1. A short and catchy title for the image.
        2. A detailed description of what is happening in the image.

        Format the response as:
        Title: <short title here>
        Description: <detailed description here>
        """

        print("Sending image and improved prompt to Gemini AI...")  # Debugging log

        response = model.generate_content([prompt, image], stream=False)

        if not response or not hasattr(response, "parts") or not response.parts:
            print(f"Gemini AI response error: {response}")  # Debugging log
            return {"title": "Error", "description": "Gemini AI returned an empty response"}

        response_text = response.parts[0].text.strip()  # Extract response text

        # FIX: Extract title and description properly
        title = "Unknown"
        description = "No description available"

        for line in response_text.split("\n"):
            if line.lower().startswith("title:"):
                title = line.split("Title:", 1)[1].strip()
            elif line.lower().startswith("description:"):
                description = line.split("Description:", 1)[1].strip()

        return {"title": title, "description": description}

    except Exception as e:
        print(f"Error processing image: {e}")
        return {"title": "Error", "description": f"Could not generate caption: {e}"}


def save_json_metadata(filename, metadata):
    """Saves metadata (title, description) as a JSON file in Google Cloud Storage."""
    json_blob_name = filename.replace(".jpeg", ".json").replace(".jpg", ".json")
    blob = bucket.blob(json_blob_name)
    blob.upload_from_string(json.dumps(metadata), content_type="application/json")


@app.route('/upload', methods=["POST"])
def upload():
    file = request.files['form_file']
    filename = file.filename
    file.seek(0)  # Reset file pointer to the beginning

    # Upload image to GCS
    image_uri = upload_blob(file, filename)

    # Generate metadata using Gemini AI
    file.seek(0)  # Reset again before sending to AI
    image_data = file.read()
    metadata = generate_image_caption(image_data)  # FIX: Pass converted image

    # Save metadata as JSON in GCS
    save_json_metadata(filename, metadata)

    return redirect("/")


def list_files():
    """Lists all JPEG/JPG files in the Google Cloud Storage bucket."""
    blobs = bucket.list_blobs()
    return [blob.name for blob in blobs if blob.name.lower().endswith(('.jpeg', '.jpg'))]


@app.route('/files/<filename>')
def get_file(filename):
    """Retrieves an image file from Google Cloud Storage and returns it."""
    blob = bucket.blob(filename)
    image_data = blob.download_as_bytes()
    return send_file(BytesIO(image_data), mimetype='image/jpeg')


if __name__ == '__main__':
    app.run(debug=True)

