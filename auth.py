import random
import smtplib
import os
from email.message import EmailMessage
from supabase import create_client

EMAIL_USER = "dinoboyadi@gmail.com"
EMAIL_PASSWORD = "esahoznfsipmqjcq"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_session(sender):
    res = supabase.table("user_sessions").select("*").eq("whatsapp", sender).execute()
    return res.data[0] if res.data else {}

def update_session(sender, data: dict):
    current = get_session(sender)
    updated = {**current, **data, "whatsapp": sender}
    supabase.table("user_sessions").upsert(updated).execute()

def clear_user(sender):
    supabase.table("user_sessions").delete().eq("whatsapp", sender).execute()

def get_user_state(sender): return get_session(sender).get("state")
def set_user_state(sender, state): update_session(sender, {"state": state})

def get_user_email(sender): return get_session(sender).get("email")
def set_user_email(sender, email): update_session(sender, {"email": email})

def get_user_otp(sender): return get_session(sender).get("otp")
def set_user_otp(sender, otp): update_session(sender, {"otp": otp})

def get_user_intent(sender): return get_session(sender).get("intent", "unknown")
def set_user_intent(sender, intent): update_session(sender, {"intent": intent})

def is_authenticated(sender): return get_user_email(sender) is not None
def mark_authenticated(sender): pass

def send_otp_email(to_email: str, otp: str):
    msg = EmailMessage()
    msg.set_content(f"Your FinBot verification code is: {otp}")
    msg["Subject"] = "Your FinBot OTP Code"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
            print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Email error: {e}")

def generate_and_send_otp(sender, email):
    otp = str(random.randint(100000, 999999))
    set_user_otp(sender, otp)
    set_user_state(sender, "awaiting_otp")
    send_otp_email(email, otp)
