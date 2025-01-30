import os
from flask import Flask, redirect ,request, send_file

from google.cloud import storage

app = Flask(__name__)

os.makedirs('files', exist_ok = True)
bucket_name = 'cnd-z23746774-bucket'

@app.route('/')
def index():
  index_html=""" 
  <form method="post" enctype="multipart/form-data" action="/upload" method="post">
  <div>
    <label for="file">Choose file to upload</label>
    <input type="file" id="file" name="form_file" accept="image/jpeg"/>
  </div>
  <div>
    <button>Submit</button>
  </div>
</form>"""

  for file in list_files():
        index_html += "<li><a href=\"/files/" + file + "\">" + file + "</a></li>"

  return index_html

def upload_blob(bucket_name, file, destination_blob_name):
  storage.client = storage.Client()
  bucket = storage.client.bucket(bucket_name)
  blob = bucket.blob(destination_blob_name)
  blob.upload_from_file(file)

@app.route('/upload', methods=["POST"])
def upload():
    file = request.files['form_file']  # item name must match name in HTML form
    filename = file.filename
    file.save(os.path.join("./files", filename))
    file.seek(0)
    upload_blob(bucket_name, file, filename)
    return redirect("/")

@app.route('/files')
def list_files():
    files = os.listdir("./files")
    jpegs = []
    for file in files:
        if file.lower().endswith(".jpeg") or file.lower().endswith(".jpg"):
            jpegs.append(file)

    return jpegs

@app.route('/files/<filename>')
def get_file(filename):
  return send_file('./files/'+filename)

if __name__ == '__main__':
    app.run(debug=True)
