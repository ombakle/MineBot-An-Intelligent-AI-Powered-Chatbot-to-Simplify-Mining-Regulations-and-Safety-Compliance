from flask import Flask, request, jsonify, render_template
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import torch
import re
import random

app = Flask(__name__)

# Load pre-trained sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Load CSV with Hindi and English questions/answers
csv_file_path = "Merged_Translated_Questions_1_to_80.csv"
def load_csv(file_path):
    df = pd.read_csv(file_path)
    required_cols = ['Question', 'Answer', 'Question_Hindi', 'Answer_Hindi']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")
    return df

# Load and prepare embeddings
try:
    data = load_csv(csv_file_path)

    questions_en = data['Question'].tolist()
    answers_en = data.set_index('Question')['Answer'].to_dict()

    questions_hi = data['Question_Hindi'].tolist()
    answers_hi = data.set_index('Question_Hindi')['Answer_Hindi'].to_dict()

    embeddings_en = model.encode(questions_en, convert_to_tensor=True)
    embeddings_hi = model.encode(questions_hi, convert_to_tensor=True)
except Exception as e:
    raise RuntimeError(f"Error loading data: {e}")

# Function to find best match from given language data
def find_best_match(user_input, lang):
    input_embedding = model.encode(user_input, convert_to_tensor=True)

    if lang == 'hi':
        sims = util.pytorch_cos_sim(input_embedding, embeddings_hi)[0]
        best_idx = torch.argmax(sims).item()
        return questions_hi[best_idx], answers_hi[questions_hi[best_idx]], sims[best_idx].item() * 100
    else:
        sims = util.pytorch_cos_sim(input_embedding, embeddings_en)[0]
        best_idx = torch.argmax(sims).item()
        return questions_en[best_idx], answers_en[questions_en[best_idx]], sims[best_idx].item() * 100

# Chat endpoint
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_input = data.get('user_input', '').strip()
        language = data.get('language', 'en')  # default to English

        greetings_en = ["hi", "hello", "hey", "hi there", "good morning", "good evening", "good afternoon"]
        greetings_hi = ["नमस्ते", "हैलो", "सुप्रभात", "शुभ संध्या", "प्रणाम", "नमस्कार"]

        # Clean punctuation only for English
        if language != 'hi':
            user_input = re.sub(r'[^\w\s]', '', user_input.lower())  # lowercase + clean
        else:
            user_input = re.sub(r'[।]', '', user_input)  # only remove danda if needed

        # Check greetings
        if (language == 'hi' and user_input in greetings_hi) or (language != 'hi' and user_input in greetings_en):
            greeting_msg = "नमस्ते! कोल माइन चैट में आपका स्वागत है। आपकी क्या सहायता कर सकता हूँ?" if language == 'hi' else "Hello! Welcome to Coal Mine Chat. How can I help you?"
            return jsonify({
                "user_input": user_input,
                "response": greeting_msg,
                "confidence": 100
            })

        # Fallback to match function
        matched_q, matched_a, confidence = find_best_match(user_input, language)

        if confidence > 70:
            return jsonify({
                "user_input": user_input,
                "closest_match": matched_q,
                "response": matched_a,
                "confidence": confidence
            })
        else:
            fallback_msg = "माफ़ कीजिए, मैं आपका प्रश्न समझ नहीं पाया। कृपया दोबारा प्रयास करें।" if language == 'hi' else "Sorry, I couldn't understand your question. Can you rephrase?"
            return jsonify({
                "user_input": user_input,
                "response": fallback_msg,
                "confidence": confidence
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# Suggest random questions
@app.route('/random_questions', methods=['GET'])
def random_questions():
    lang = request.args.get('lang', 'en')
    try:
        if lang == 'hi':
            return jsonify({"questions": random.sample(questions_hi, 2)})
        else:
            return jsonify({"questions": random.sample(questions_en, 2)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return render_template('index.html')

from flask import render_template

@app.route('/admin')
def admin_panel():
    return render_template("admin.html")

@app.route('/add_qa', methods=['POST'])
def add_qa():
    try:
        data = request.get_json()
        en_q = data.get("en_question", "").strip()
        en_a = data.get("en_answer", "").strip()
        hi_q = data.get("hi_question", "").strip()
        hi_a = data.get("hi_answer", "").strip()

        # Ensure at least one complete pair is present
        if not ((en_q and en_a) or (hi_q and hi_a)):
            return jsonify({"message": "Please fill at least English or Hindi question and answer."}), 400

        new_row = pd.DataFrame([{
            "Question": en_q if en_q else "",
            "Answer": en_a if en_a else "",
            "Question_Hindi": hi_q if hi_q else "",
            "Answer_Hindi": hi_a if hi_a else ""
        }])
        new_row.to_csv("Merged_Translated_Questions_1_to_80.csv", mode='a', index=False, header=False)

        return jsonify({"message": "Question added successfully!"})
    except Exception as e:
        return jsonify({"message": f"Failed to add entry: {str(e)}"}), 500

@app.route("/get_all_qa")
def get_all_qa():
    try:
        df = pd.read_csv("Merged_Translated_Questions_1_to_80.csv").fillna("")
        return jsonify({"entries": df.to_dict(orient="records")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/update_qa", methods=["POST"])
def update_qa():
    try:
        data = request.json
        index = int(data.get("index"))
        df = pd.read_csv("Merged_Translated_Questions_1_to_80.csv")
        df.at[index, "Question"] = data.get("en_question", "")
        df.at[index, "Answer"] = data.get("en_answer", "")
        df.at[index, "Question_Hindi"] = data.get("hi_question", "")
        df.at[index, "Answer_Hindi"] = data.get("hi_answer", "")
        df.to_csv("Merged_Translated_Questions_1_to_80.csv", index=False)
        return jsonify({"message": "Entry updated successfully."})
    except Exception as e:
        return jsonify({"message": f"Update failed: {str(e)}"}), 500


@app.route("/delete_qa", methods=["POST"])
def delete_qa():
    try:
        data = request.json
        index = int(data.get("index"))
        df = pd.read_csv("Merged_Translated_Questions_1_to_80.csv")
        df = df.drop(index).reset_index(drop=True)
        df.to_csv("Merged_Translated_Questions_1_to_80.csv", index=False)
        return jsonify({"message": "Entry deleted successfully."})
    except Exception as e:
        return jsonify({"message": f"Delete failed: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)
