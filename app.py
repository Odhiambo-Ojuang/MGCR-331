from flask import Flask, render_template, request
import fitz
from flask_cors import CORS
from groq import Groq

app = Flask(__name__, template_folder='frontend')  # Correct template folder path
CORS(app, origins=["http://127.0.0.1:5500"])

client = Groq(api_key = "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")  # Set your Groq API key

# === Extract PDF text ===
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# === Generate journal entries using AI ===
def generate_journal_entries_and_ledger(text):
  
    try:
        # Adjust Groq API call here
        response = client.chat.completions.create(
    model="llama3-8b-8192",
    messages=[
        {"role": "system", "content": "You are a helpful CPA assistant."},
        {"role": "user", "content": (
            "The user has provided a list of company financing activities, "
            "each in the format 'Date - Description of operation'.\n\n"
            "Generate formal accounting journal entries for each line, including debit and credit lines, "
            "with proper indentation. Additionally, for each journal entry, track the ending balance for each "
            "account involved in the transaction, and calculate the running balances for the entire year.\n\n"
            f"Input:\n{text}\n\nJournal Entries and Ledger Balances:"
        )}
    ],
    temperature=0.3
)
        return response.choices[0].message.content  # Correct access pattern
    except Exception as e:
        print(f"An error occurred: {e}")
        return "Failed to generate journal entries."

# === Routes ===
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process_financing_file", methods=["POST"])
def process_financing_file():
    file = request.files["financing_file"]
    
    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(file)
    elif file.filename.endswith(".txt") or file.filename.endswith(".csv"):
        text = file.read().decode("utf-8")
    else:
        return "Unsupported file type", 400

    journal_entries = generate_journal_entries_and_ledger(text)
    return render_template("results.html", entries=journal_entries)

if __name__ == "__main__":
    app.run(debug=True)