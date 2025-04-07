from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from groq import Groq
import re

app = Flask(__name__, template_folder='frontend')
CORS(app, origins=["http://127.0.0.1:5500"])

client = Groq(api_key="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")  # Replace with your key


# === Groq API call ===
global_message = None

def generate_full_response(text):
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a helpful CPA assistant."},
                {"role": "user", "content": (
                    "The user has provided a list of company financing activities, "
                    "each in the format 'Date - Description of operation'.\n\n"
                    "Generate formal accounting journal entries for each line, including debit and credit lines. "
                    "Do not track the ending balance for each account in the journal entries. Ensure that each journal entry correctly "
                    "specifies which account is being debited and which is being credited, with proper indentation. "
                    "For example, the debit account should come first, followed by the credit account.\n\n"
                    "For the ledger portion, only provide the account name, number, and ending balance for each account involved in the transaction, "
                    "without any additional calculations or running balances.\n\n"
                    "Return the journal entries first, followed by a clear section titled 'Ledger Balances:' with just the account names and numbers.\n\n"
                    f"Input:\n{text}\n\nJournal Entries and Ledger Balances:"
                )}
            ],
            temperature=0.3
        )
        global global_message
        global_message = response.choices[0].message.content
        return global_message
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

    if file.filename.endswith(".txt") or file.filename.endswith(".csv"):
        text = file.read().decode("utf-8")
    else:
        return "Unsupported file type", 400

    full_response = generate_full_response(text)
    journal, ledger = split_journal_and_ledger(full_response)

    return render_template("results.html", entries=journal, ledger=ledger)

@app.route("/update_balance_sheet", methods=["POST"])
def update_balance_sheet():
    if global_message is None:
        return "AI response is not available. Please upload a financing file first.", 400

    # Get the ledger portion
    _, ledger = split_journal_and_ledger(global_message)

    # Get uploaded balance sheet
    balance_sheet_file = request.files.get('balance_sheet_file')
    if not balance_sheet_file:
        return "Balance sheet file is required", 400

    # Read balance sheet text
    if balance_sheet_file.filename.endswith('.txt') or balance_sheet_file.filename.endswith('.csv'):
        balance_sheet_text = balance_sheet_file.read().decode("utf-8")
    else:
        return "Invalid file format for balance sheet", 400

    # Ask AI to add ledger amounts to balance sheet
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a helpful CPA assistant."},
                {"role": "user", "content": (
                    "Here is the company's previous balance sheet:\n\n"
                    f"{balance_sheet_text}\n\n"
                    "And here are the new ledger balances from financing activity:\n\n"
                    f"{ledger}\n\n"
                    "Please add the ledger balances to the appropriate accounts in the balance sheet. "
                    "If an account in the ledger does not exist in the balance sheet, add it. "
                    "Return only the updated balance sheet in the format:\n"
                    "Account Name: updated amount"
                )}
            ],
            temperature=0.2
        )
        updated_balance_sheet = response.choices[0].message.content
        return render_template("update.html", updated_sheet=updated_balance_sheet)

    except Exception as e:
        print(f"AI balance sheet update error: {e}")
        return "Failed to update balance sheet using AI.", 500

if __name__ == "__main__":
    app.run(debug=True)
