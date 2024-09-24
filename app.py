from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
import json
import os
from flask_cors import CORS  # Import CORS


app = Flask(__name__)

""" Enable CORS for the entire Flask app """
""" MongoDB configuration (replace with your MongoDB URI) """
CORS(app)
app.config["MONGO_URI"] = "mongodb://localhost:27017/mydatabase"
mongo = PyMongo(app)

""" Folder to store uploaded files temporarily (optional) """
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

""" Ensure the upload folder exists """
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


from bson import ObjectId
from datetime import datetime

def parse_json_data(data):
    """Recursively parse the JSON data to handle MongoDB-specific issues like '$date'."""
    if isinstance(data, dict):
        parsed_data = {}
        for key, value in data.items():
            if isinstance(value, dict) and "$date" in value:
                parsed_data[key] = datetime.strptime(value["$date"], "%Y-%m-%dT%H:%M:%S.%fZ")   # Convert $date to Python datetime 
            else:
                parsed_data[key] = parse_json_data(value)
        return parsed_data
    elif isinstance(data, list):
        return [parse_json_data(item) for item in data]
    else:
        return data

@app.route('/upload-json', methods=['POST'])
def upload_json():
    if 'file' not in request.files:
        return jsonify({"message": "No file part in the request"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No file selected"}), 400
    
    if file and file.filename.endswith('.json'):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            with open(filepath, 'r') as json_file:
                data = json.load(json_file)  
            
            parsed_data = parse_json_data(data)

            for item in parsed_data:
                if '_id' in item and '$oid' in item['_id']:  
                    """ Use ObjectId for MongoDB _id
                        Remove the _id from the item, since we can't update _id directly """
                    object_id = ObjectId(item['_id']['$oid'])
                    del item['_id']
                    """ Update the data in MongoDB using the _id field
                        Search by _id 
                        Update with new data
                        Insert if not found"""
                    mongo.db.mycollection.update_one(
                        {'_id': object_id},  
                        {'$set': item},      
                        upsert=True          
                    )
                else:
                    print("Skipping item without valid _id:", item)

            return jsonify({"message": "JSON file uploaded and data updated in MongoDB."}), 200
        
        except Exception as e:
            print(f"Error processing file: {e}")
            return jsonify({"message": "Failed to process file", "error": str(e)}), 500
    else:
        return jsonify({"message": "Invalid file format. Please upload a JSON file."}), 400


if __name__ == '__main__':
    app.run(debug=True)
