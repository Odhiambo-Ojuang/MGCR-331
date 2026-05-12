import os
import re

from flask import Flask, render_template, request
from flask_cors import CORS
from groq import Groq

from financial_agent import FinancialAgent

app = Flask(__name__, template_folder="frontend")

CORS(app, origins=[
    "http://127.0.0.1:5500",
    "https://cpavalsoft.onrender.com",
])

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Single-user demo state: the agent built up while processing the financing
# file is reused when the user uploads a balance sheet. (Matches the original
# `global_message` pattern; replace with per-session storage for multi-user.)
_session: dict[str, FinancialAgent | str | None] = {"agent": None, "last_response": None}


def _split_journal_and_ledger(text: str) -> tuple[str, str]:
    match = re.search(r"\*\*Ledger Balances:\*\*|Ledger Balances:", text)
    if not match:
        return text, "Could not extract ledger section."
    idx = match.start()
    return text[:idx].strip(), text[idx:].strip()


def _read_text_upload(file_storage) -> str:
    return file_storage.read().decode("utf-8")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process_financing_file", methods=["POST"])
def process_financing_file():
    if "financing_file" not in request.files:
        return "No financing file uploaded.", 400

    file = request.files["financing_file"]
    if not file.filename:
        return "No selected file.", 400
    if not (file.filename.endswith(".txt") or file.filename.endswith(".csv")):
        return "Unsupported file type. Please upload a .txt or .csv file.", 400

    operations_text = _read_text_upload(file)

    agent = FinancialAgent(client)
    try:
        response_text = agent.process_financing_operations(operations_text)
    except Exception as exc:  # noqa: BLE001 - surface agent failures to the user
        print(f"Agent error (financing): {exc}")
        return f"Failed to generate journal entries and ledger. Error: {exc}", 500

    _session["agent"] = agent
    _session["last_response"] = response_text

    journal, ledger = _split_journal_and_ledger(response_text)
    return render_template("results.html", entries=journal, ledger=ledger)


@app.route("/update_balance_sheet", methods=["POST"])
def update_balance_sheet():
    agent = _session.get("agent")
    if not isinstance(agent, FinancialAgent):
        return "AI response is not available. Please upload a financing file first.", 400

    balance_sheet_file = request.files.get("balance_sheet_file")
    if not balance_sheet_file or not balance_sheet_file.filename:
        return "Balance sheet file is required.", 400
    if not (
        balance_sheet_file.filename.endswith(".txt")
        or balance_sheet_file.filename.endswith(".csv")
    ):
        return "Invalid file format for balance sheet. Please upload a .txt or .csv file.", 400

    balance_sheet_text = _read_text_upload(balance_sheet_file)

    try:
        updated_balance_sheet = agent.process_balance_sheet_update(balance_sheet_text)
        return render_template("update.html", updated_sheet=updated_balance_sheet)
    except Exception as exc:  # noqa: BLE001
        print(f"Agent error (balance sheet): {exc}")
        return f"Failed to update balance sheet using AI. Error: {exc}", 500


if __name__ == "__main__":
    app.run(debug=True)
