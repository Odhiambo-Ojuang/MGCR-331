from flask import Flask, render_template, request
import fitz
from flask_cors import CORS
from groq import Groq
import re

app = Flask(__name__, template_folder='frontend')
CORS(app, origins=["http://127.0.0.1:5500"])

client = Groq(api_key="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")  # Replace with yours

# === Extract PDF text ===
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# === Groq API call ===
def generate_full_response(text):
    try:
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
                    "Return the journal entries first, then a clear section titled 'Ledger Balances:' followed by the ledger."
                    f"\n\nInput:\n{text}\n\nJournal Entries and Ledger Balances:"
                )}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Groq error: {e}")
        return "Failed to generate journal entries and ledger."

# === Split response into journal and ledger ===
def split_journal_and_ledger(full_response):
    try:
        match = re.search(r"\*\*Ledger Balances:\*\*|\nLedger Balances:", full_response)
        if match:
            split_index = match.start()
            journal = full_response[:split_index].strip()
            ledger = full_response[split_index:].strip()
        else:
            journal = full_response
            ledger = "Could not extract ledger section."
        return journal, ledger

    except Exception as e:
        print(f"Splitting error: {e}")
        return full_response, "Could not extract ledger section."

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

    full_response = generate_full_response(text)
    journal, ledger = split_journal_and_ledger(full_response)

    return render_template("results.html", entries=journal, ledger=ledger)

if __name__ == "__main__":
    app.run(debug=True)