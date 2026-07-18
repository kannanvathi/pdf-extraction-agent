"""Send a daily DVA-C02 practice question via SendGrid email."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

QUESTIONS_FILE = Path(__file__).parent / "questions.json"


def load_questions() -> list[dict]:
    with open(QUESTIONS_FILE) as f:
        return json.load(f)


def pick_question(questions: list[dict]) -> dict:
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    return questions[day_of_year % len(questions)]


def build_html(question: dict, day_number: int) -> str:
    options_html = "".join(
        f"<li style='margin:6px 0;font-size:15px;'><b>{k})</b> {v}</li>"
        for k, v in question["options"].items()
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
<div style="max-width:600px;margin:auto;background:#ffffff;border-radius:10px;padding:30px;box-shadow:0 2px 6px rgba(0,0,0,0.1);">

  <h2 style="color:#232f3e;text-align:center;margin-bottom:5px;">
    📚 DVA-C02 Daily Question #{day_number}
  </h2>
  <p style="text-align:center;color:#666;font-size:13px;margin-top:0;">
    Domain: <b>{question['domain']}</b> &nbsp;|&nbsp; {datetime.now(timezone.utc).strftime('%B %d, %Y')}
  </p>
  <hr style="border:none;border-top:1px solid #eee;">

  <p style="font-size:16px;color:#333;line-height:1.6;"><b>Q{question['id']}. {question['question']}</b></p>

  <ul style="list-style:none;padding:0;">{options_html}</ul>

  <div style="background:#e6f7ed;border-left:4px solid #00a65a;padding:15px;margin:20px 0;border-radius:4px;">
    <p style="margin:0;font-size:15px;color:#1a7a3a;"><b>✅ Answer: {question['answer']}) {question['options'][question['answer']]}</b></p>
  </div>

  <div style="background:#fff8e1;border-left:4px solid #f9a825;padding:15px;margin:20px 0;border-radius:4px;">
    <p style="margin:0;font-size:14px;color:#5d4037;"><b>💡 Explanation:</b> {question['explanation']}</p>
  </div>

  <hr style="border:none;border-top:1px solid #eee;">
  <p style="text-align:center;color:#999;font-size:12px;">
    🎯 Tip: Score 80%+ on practice tests before booking your exam.<br>
    Practice links: 
    <a href="https://www.examcert.app/exams/aws-dva-c02/free-practice-test/">ExamCert</a> |
    <a href="https://certificationpractice.com/practice-exams/aws-certified-developer-associate">CertPractice</a>
  </p>

</div>
</body>
</html>"""


def send_email(html: str, subject: str) -> None:
    api_key = os.environ.get("SENDGRID_API_KEY")
    sender = os.environ.get("SENDER_EMAIL")
    recipient = os.environ.get("RECIPIENT_EMAIL")

    if not all([api_key, sender, recipient]):
        print("ERROR: Missing SENDGRID_API_KEY, SENDER_EMAIL, or RECIPIENT_EMAIL env vars")
        sys.exit(1)

    message = Mail(
        from_email=sender,
        to_emails=recipient,
        subject=subject,
        html_content=html,
    )

    try:
        client = SendGridAPIClient(api_key)
        response = client.send(message)
        print(f"Email sent! Status: {response.status_code}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        sys.exit(1)


def main():
    questions = load_questions()
    question = pick_question(questions)
    day_number = (datetime.now(timezone.utc).timetuple().tm_yday % len(questions)) + 1

    subject = f"📚 DVA-C02 Question #{day_number} — {question['domain']}"
    html = build_html(question, day_number)

    print(f"Today's question: #{question['id']} ({question['domain']})")
    send_email(html, subject)


if __name__ == "__main__":
    main()
