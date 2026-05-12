"""Tool-using financial agent.

The LLM is responsible only for *reasoning* about which accounts to debit and
credit for each operation. All arithmetic (journal aggregation, ledger ending
balances, balance-sheet updates) happens deterministically in the tools defined
below, so the numbers the user sees are always reproducible and correct.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


# Standard chart of accounts. Each entry maps a canonical account name to its
# account number and accounting type. Types drive the normal-balance logic.
CHART_OF_ACCOUNTS: dict[str, dict[str, str]] = {
    # Assets (debit-normal)
    "Cash": {"number": "101", "type": "asset"},
    "Accounts Receivable": {"number": "105", "type": "asset"},
    "Inventory": {"number": "110", "type": "asset"},
    "Marketable Securities": {"number": "115", "type": "asset"},
    "Prepaid Expenses": {"number": "120", "type": "asset"},
    "Office Equipment": {"number": "150", "type": "asset"},
    "Property, Plant, and Equipment": {"number": "155", "type": "asset"},
    "Intangible Assets": {"number": "160", "type": "asset"},
    "Goodwill": {"number": "165", "type": "asset"},
    # Liabilities (credit-normal)
    "Accounts Payable": {"number": "201", "type": "liability"},
    "Short-term Debt": {"number": "210", "type": "liability"},
    "Notes Payable": {"number": "215", "type": "liability"},
    "Current Portion of Long-term Debt": {"number": "218", "type": "liability"},
    "Long-term Debt": {"number": "220", "type": "liability"},
    "Bonds Payable": {"number": "225", "type": "liability"},
    # Equity (credit-normal except contra-equity accounts)
    "Common Stock": {"number": "301", "type": "equity"},
    "Preferred Shares": {"number": "305", "type": "equity"},
    "Additional Paid-in Capital": {"number": "310", "type": "equity"},
    "Retained Earnings": {"number": "320", "type": "equity"},
    "Dividends": {"number": "325", "type": "contra-equity"},
    "Treasury Stock": {"number": "330", "type": "contra-equity"},
    # Revenue (credit-normal)
    "Revenue": {"number": "401", "type": "revenue"},
    "Sales Revenue": {"number": "402", "type": "revenue"},
    "Interest Income": {"number": "410", "type": "revenue"},
    # Expenses (debit-normal)
    "Interest Expense": {"number": "501", "type": "expense"},
    "Operating Expense": {"number": "510", "type": "expense"},
}

DEBIT_NORMAL_TYPES = {"asset", "expense", "contra-equity", "contra-asset"}

CHART_OF_ACCOUNTS_DESC = "\n".join(
    f"- {name} (#{info['number']}, {info['type']})"
    for name, info in CHART_OF_ACCOUNTS.items()
)


def _account_info(account_name: str) -> dict[str, str]:
    if account_name in CHART_OF_ACCOUNTS:
        return {"name": account_name, **CHART_OF_ACCOUNTS[account_name]}
    lower = account_name.strip().lower()
    for name, info in CHART_OF_ACCOUNTS.items():
        if name.lower() == lower:
            return {"name": name, **info}
    return {"name": account_name, "number": "—", "type": "unknown"}


def _normal_balance(account_type: str) -> str:
    return "debit" if account_type in DEBIT_NORMAL_TYPES else "credit"


class FinancialAgent:
    """An LLM agent that uses tools to keep its math honest."""

    def __init__(self, client: Any, model: str = "llama-3.3-70b-versatile") -> None:
        self.client = client
        self.model = model
        self.journal_entries: list[dict[str, Any]] = []

    # ---------------------------------------------------------------
    # Tool implementations (deterministic)
    # ---------------------------------------------------------------

    def _tool_record_journal_entry(
        self,
        date: str,
        description: str,
        debit_account: str,
        credit_account: str,
        amount: float,
    ) -> dict[str, Any]:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {"error": f"Invalid amount: {amount!r}. Must be a number."}
        if amount <= 0:
            return {"error": "Amount must be positive; use debit/credit roles for direction."}
        if not debit_account or not credit_account:
            return {"error": "Both debit_account and credit_account are required."}
        if debit_account.strip().lower() == credit_account.strip().lower():
            return {"error": "Debit and credit accounts must differ."}

        entry = {
            "date": date.strip(),
            "description": description.strip(),
            "debit_account": debit_account.strip(),
            "credit_account": credit_account.strip(),
            "amount": round(amount, 2),
        }
        self.journal_entries.append(entry)
        return {
            "status": "recorded",
            "entry_number": len(self.journal_entries),
            "entry": entry,
        }

    def _tool_get_journal_entries(self) -> dict[str, Any]:
        return {"count": len(self.journal_entries), "entries": list(self.journal_entries)}

    def _tool_compute_ledger_balances(self) -> dict[str, Any]:
        running: dict[str, dict[str, float]] = {}
        for e in self.journal_entries:
            for side, account in (("debit", e["debit_account"]), ("credit", e["credit_account"])):
                bucket = running.setdefault(account, {"debits": 0.0, "credits": 0.0})
                bucket[f"{side}s"] += e["amount"]

        ledger: list[dict[str, Any]] = []
        for name in sorted(running):
            info = _account_info(name)
            account_type = info["type"]
            normal = _normal_balance(account_type) if account_type != "unknown" else "debit"
            debits = running[name]["debits"]
            credits = running[name]["credits"]
            ending = debits - credits if normal == "debit" else credits - debits
            ledger.append(
                {
                    "account_name": name,
                    "account_number": info["number"],
                    "account_type": account_type,
                    "normal_balance": normal,
                    "total_debits": round(debits, 2),
                    "total_credits": round(credits, 2),
                    "ending_balance": round(ending, 2),
                }
            )
        return {"ledger": ledger}

    def _tool_lookup_account(self, account_name: str) -> dict[str, Any]:
        return _account_info(account_name)

    def _tool_parse_balance_sheet(self, balance_sheet_text: str) -> dict[str, Any]:
        # Pulls "<name>   $<amount>" / "- <name>   <amount>" lines out of a textual
        # balance sheet while ignoring section headers and Total rows.
        accounts: list[dict[str, Any]] = []
        current_section: Optional[str] = None
        section_pat = re.compile(
            r"^\s*(Assets|Liabilities|Equity|Liabilities\s*&\s*Equity|Current Assets|"
            r"Non-Current Assets|Current Liabilities|Long-term Liabilities)\s*$",
            re.IGNORECASE,
        )
        line_pat = re.compile(r"^\s*[-•]?\s*(.+?)\s+\$?([\d,]+(?:\.\d+)?)\s*$")

        for raw in balance_sheet_text.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            if section_pat.match(line):
                current_section = line.strip()
                continue
            m = line_pat.match(line)
            if not m:
                continue
            name = m.group(1).strip().strip("-").strip()
            if name.lower().startswith("total"):
                continue
            try:
                amount = float(m.group(2).replace(",", ""))
            except ValueError:
                continue
            accounts.append({"name": name, "amount": amount, "section": current_section})
        return {"accounts": accounts}

    def _tool_apply_ledger_to_balance_sheet(self, balance_sheet_text: str) -> dict[str, Any]:
        parsed = self._tool_parse_balance_sheet(balance_sheet_text)
        bs: dict[str, dict[str, Any]] = {a["name"]: dict(a) for a in parsed["accounts"]}
        ledger = self._tool_compute_ledger_balances()["ledger"]

        updates: list[dict[str, Any]] = []
        for item in ledger:
            ledger_name = item["account_name"]
            change = item["ending_balance"]
            if change == 0:
                continue

            # Try exact (case-insensitive) match first, then substring fallback.
            match: Optional[str] = next(
                (n for n in bs if n.lower() == ledger_name.lower()),
                None,
            )
            if match is None:
                match = next(
                    (
                        n
                        for n in bs
                        if ledger_name.lower() in n.lower() or n.lower() in ledger_name.lower()
                    ),
                    None,
                )

            if match:
                old = bs[match]["amount"]
                new = round(old + change, 2)
                bs[match]["amount"] = new
                updates.append(
                    {
                        "account": match,
                        "previous_amount": round(old, 2),
                        "change": round(change, 2),
                        "new_amount": new,
                        "action": "updated",
                    }
                )
            else:
                bs[ledger_name] = {
                    "name": ledger_name,
                    "amount": round(change, 2),
                    "section": _account_info(ledger_name)["type"],
                }
                updates.append(
                    {
                        "account": ledger_name,
                        "previous_amount": 0.0,
                        "change": round(change, 2),
                        "new_amount": round(change, 2),
                        "action": "added",
                    }
                )

        return {
            "updated_balance_sheet": list(bs.values()),
            "updates": updates,
        }

    # ---------------------------------------------------------------
    # Tool registry (Groq / OpenAI-compatible JSON schemas)
    # ---------------------------------------------------------------

    def _tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "record_journal_entry",
                    "description": (
                        "Record one double-entry journal entry. Call this exactly once "
                        "per financing operation. The debit account is debited and the "
                        "credit account is credited by the same positive amount."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Transaction date, e.g. 'January 5, 2024'."},
                            "description": {"type": "string", "description": "Concise description of the operation."},
                            "debit_account": {"type": "string", "description": "Name of the account being debited."},
                            "credit_account": {"type": "string", "description": "Name of the account being credited."},
                            "amount": {"type": "number", "description": "Positive transaction amount in dollars."},
                        },
                        "required": [
                            "date",
                            "description",
                            "debit_account",
                            "credit_account",
                            "amount",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_journal_entries",
                    "description": "Return every journal entry recorded so far.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compute_ledger_balances",
                    "description": (
                        "Aggregate all recorded journal entries into ending ledger balances "
                        "per account. Call this AFTER every operation has been recorded. "
                        "Never compute balances yourself — this tool is the source of truth."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "lookup_account",
                    "description": "Look up the standard account number and type for an account name.",
                    "parameters": {
                        "type": "object",
                        "properties": {"account_name": {"type": "string"}},
                        "required": ["account_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_ledger_to_balance_sheet",
                    "description": (
                        "Deterministically apply current ledger ending balances onto a "
                        "previous balance sheet. Updates existing rows and adds missing "
                        "ones with exact arithmetic. Use this for every balance-sheet "
                        "update — never do the math yourself."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "balance_sheet_text": {
                                "type": "string",
                                "description": "Raw text of the previous balance sheet.",
                            }
                        },
                        "required": ["balance_sheet_text"],
                    },
                },
            },
        ]

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        dispatch = {
            "record_journal_entry": self._tool_record_journal_entry,
            "get_journal_entries": self._tool_get_journal_entries,
            "compute_ledger_balances": self._tool_compute_ledger_balances,
            "lookup_account": self._tool_lookup_account,
            "apply_ledger_to_balance_sheet": self._tool_apply_ledger_to_balance_sheet,
        }
        fn = dispatch.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return fn(**arguments)
        except TypeError as exc:
            return {"error": f"Invalid arguments for {name}: {exc}"}
        except Exception as exc:  # noqa: BLE001 - surface any tool failure to the model
            return {"error": f"Tool {name} raised: {exc}"}

    # ---------------------------------------------------------------
    # Agent loop
    # ---------------------------------------------------------------

    def _run(self, system_prompt: str, user_message: str, max_iterations: int = 20) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        tools = self._tool_specs()

        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = response.choices[0].message

            assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)

            if not msg.tool_calls:
                return msg.content or ""

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._execute_tool(tc.function.name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str),
                    }
                )

        return "Agent reached the maximum tool-use iterations without producing a final answer."

    # ---------------------------------------------------------------
    # Public workflows
    # ---------------------------------------------------------------

    def process_financing_operations(self, operations_text: str) -> str:
        system_prompt = (
            "You are a CPA agent that produces accurate journal entries and ledger "
            "balances for company financing operations.\n\n"
            "You MUST use tools — never compute balances yourself. The tools handle "
            "arithmetic deterministically; your job is to interpret each operation and "
            "choose the correct debit and credit accounts.\n\n"
            "Workflow:\n"
            "1. Parse the operations text. For each operation, determine the date, a "
            "concise description, the amount, and the correct debit/credit accounts "
            "using standard double-entry accounting rules.\n"
            "2. Call `record_journal_entry` exactly once per operation.\n"
            "3. When every operation has been recorded, call `compute_ledger_balances` "
            "to obtain the ending ledger.\n"
            "4. Send a FINAL assistant message (no more tool calls) formatted EXACTLY "
            "like this:\n\n"
            "Journal Entries:\n"
            "1. <Date> — <Description>\n"
            "   Debit:  <Account> $<amount>\n"
            "   Credit: <Account> $<amount>\n"
            "2. ...\n\n"
            "Ledger Balances:\n"
            "<Account Name> (#<Number>): $<ending balance>\n"
            "...\n\n"
            "Guidance:\n"
            "- For dividends paid, debit Retained Earnings (not a Dividends account) "
            "so the balance sheet update reduces equity correctly.\n"
            "- Prefer these canonical account names so the tools can match them to "
            "the balance sheet:\n"
            f"{CHART_OF_ACCOUNTS_DESC}\n"
            "- If a transaction needs an account not listed, pick a sensible standard "
            "name and reuse it consistently."
        )
        user_message = f"Financing operations to process:\n\n{operations_text}"
        return self._run(system_prompt, user_message)

    def process_balance_sheet_update(self, balance_sheet_text: str) -> str:
        if not self.journal_entries:
            return (
                "No journal entries have been recorded yet. Process the financing "
                "operations file first."
            )
        system_prompt = (
            "You are a CPA agent that updates balance sheets using a tool.\n\n"
            "You MUST call `apply_ledger_to_balance_sheet` exactly once with the "
            "provided balance sheet text. Never do the arithmetic yourself.\n\n"
            "After the tool returns, send a FINAL assistant message (no more tool "
            "calls) formatted as:\n\n"
            "Updated Balance Sheet\n"
            "====================\n"
            "<Account Name>: $<amount>\n"
            "<Account Name>: $<amount>\n"
            "...\n\n"
            "Use the exact numbers from the tool result. Group related accounts on "
            "consecutive lines when reasonable, but do not change the values."
        )
        user_message = f"Previous balance sheet to update:\n\n{balance_sheet_text}"
        return self._run(system_prompt, user_message)
