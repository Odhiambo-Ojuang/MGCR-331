# 📊 AI-Powered Financing Journal & Balance Sheet Processor

This project is a Flask-based web application that leverages the Groq API to automate accounting workflows. It generates journal entries, extracts ledger balances, and updates balance sheets based on user-uploaded financing activity files.

---

## 🚀 Features

- Upload financing activity files (.txt or .csv)
- Automatically generate:
  - Formal journal entries
  - Corresponding ledger balances
- Upload an existing balance sheet and:
  - Automatically update account balances
  - Add missing accounts if needed
- Simple web interface using Flask templates

---

## 🧠 How It Works

1. User uploads a financing file (list of transactions)
2. The app sends the data to the Groq LLM API
3. The AI returns:
   - Structured journal entries
   - A ledger summary
4. The app splits and displays the results
5. Optionally, the user uploads a balance sheet which is updated using the ledger data

---

## 🏗️ Project Structure

project/
│── app.py  
│── frontend/  
│   ├── index.html  
│   ├── results.html  
│   └── update.html  

---

## ⚙️ Installation

1. Clone the repository  
git clone https://github.com/your-username/your-repo.git  
cd your-repo  

2. Install dependencies  
pip install flask flask-cors groq  

3. Set your API key  
Replace in app.py:  
client = Groq(api_key="your_api_key_here")

---

## ▶️ Running the App

python app.py  

Open in browser:  
http://127.0.0.1:5000  

Open in render:
https://cpavalsoft.onrender.com

---

## 📄 Input Format

Example financing file:

2024-01-01 - Issued shares for cash  
2024-01-05 - Took bank loan  
2024-01-10 - Paid dividends  

---

## 🔄 Workflow

Step 1: Upload Financing File  
- Generates Journal Entries and Ledger Balances  

Step 2: Update Balance Sheet  
- Upload an existing balance sheet  
- AI updates values using ledger data  

---

## ⚠️ Important Notes

- Only .txt and .csv files are supported  
- AI-generated outputs should be reviewed before real accounting use  
- Do not hardcode API keys in production  

---

## 🔐 Security Recommendations

Use environment variables:  
export GROQ_API_KEY=your_key_here  

---

## 🛠️ Core Functions

- generate_full_response(text) → Sends financing data to AI  
- split_journal_and_ledger(response) → Separates journal and ledger  
- /process_financing_file → Handles file upload  
- /update_balance_sheet → Updates balance sheet  

---

## 📚 Technologies Used

- Python (Flask)  
- Groq API  
- HTML (Jinja templates)  
- Regex  

---

## 🧪 Example Output

Journal Entry:  
Cash                Dr   10,000  
   Share Capital        Cr   10,000  

Ledger Balances:  
Cash (101): 10,000  
Share Capital (301): 10,000  

---

## 📌 Future Improvements

- Add authentication system  
- Support Excel files (.xlsx)  
- Improve parsing reliability  
- Add downloadable reports  

---

## 👩🏽‍💻 Author
Nigel Odhiambo Ojuang
