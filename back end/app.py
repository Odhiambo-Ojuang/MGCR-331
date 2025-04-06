from flask import Flask, render_template, request
import openai
import fitz  # PyMuPDF for PDFs

app = Flask(__name__)

openai.api_key = "your-openai-api-key"  # Set your OpenAI API key

# === Extract PDF text ===
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# === Generate journal entries using AI ===
def generate_journal_entries_and_ledger(text):
    prompt = (
        "You are a CPA assistant. The user has provided a list of company financing activities, "
        "each in the format 'Date - Description of operation'.\n\n"
        "Generate formal accounting journal entries for each line, including debit and credit lines, "
        "with proper indentation. Additionally, for each journal entry, track the ending balance for each "
        "account involved in the transaction, and calculate the running balances for the entire year.\n\n"
        f"Input:\n{text}\n\nJournal Entries and Ledger Balances:"
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return response['choices'][0]['message']['content']

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