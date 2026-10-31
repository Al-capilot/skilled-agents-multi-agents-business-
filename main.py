import os
import math
import requests
import imageio
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from crewai_tools import SerperDevTool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_audioclips, concatenate_videoclips
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Ffmpeg asılılığı təmin edilir
try:
    imageio.plugins.ffmpeg.download()
except Exception:
    pass

# ==========================================
# 1. API AÇARLARI VƏ MÜHİT DƏYƏRLƏRİ
# ==========================================
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY", "")
os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Modellərin təyin edilməsi
llm_openai = ChatOpenAI(model="gpt-4o", temperature=0.2)
llm_gemini = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)

# ==========================================
# 2. XÜSUSİ ALƏTLƏR (TOOLS)
# ==========================================
search_tool = SerperDevTool()

@tool("WhatsApp Mesajı Göndər")
def whatsapp_mesaj_gonder(telefon_nomresi: str, mesaj_metni: str):
    """WhatsApp vasitəsilə avtomatik mesaj göndərir."""
    url = f"https://facebook.com{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": telefon_nomresi, "type": "text", "text": {"body": mesaj_metni}}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        return "WhatsApp mesajı uğurla göndərildi." if response.status_code == 200 else f"Xəta: {response.text}"
    except Exception as e:
        return f"Bağlantı xətası: {e}"

@tool("Müştəriyə Zəng Et")
def musteriye_zeng_et(telefon_nomresi: str, danisiq_metni: str):
    """Süni intellekt səsi ilə zəng edir."""
    url = "https://vapi.ai"
    headers = {"Authorization": f"Bearer {VAPI_API_KEY}", "Content-Type": "application/json"}
    payload = {"phoneNumber": telefon_nomresi, "assistant": {"model": {"provider": "openai", "model": "gpt-4o"}, "firstMessage": danisiq_metni}}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        return "Zəng uğurla başladıldı." if response.status_code == 201 else f"Zəng xətası: {response.text}"
    except Exception as e:
        return f"Zəng xətası: {e}"

@tool("WordPress Paylaşımı")
def wordpress_paylas(basliq: str, mezmun: str, status: str = "draft"):
    """Məqaləni WordPress saytına qaralama olaraq yükləyir."""
    wp_url = "https://sizin-sayt.com"
    auth = ("WP_ISTIFADECI_ADI", "WP_APPLICATION_PASSWORD")
    payload = {"title": basliq, "content": mezmun, "status": status}
    try:
        response = requests.post(wp_url, json=payload, auth=auth, timeout=15)
        return "Məqalə WordPress-ə qaralama olaraq əlavə edildi." if response.status_code == 201 else f"WP Xəta: {response.text}"
    except Exception as e:
        return f"WP Bağlantı xətası: {e}"

@tool("PDF Hesabat Yarat")
def pdf_hesabat_arat(fayl_adi: str, basliq: str, metin_mezmunu: str):
    """Rəsmi PDF sənədi yaradır."""
    doc = SimpleDocTemplate(fayl_adi, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, spaceAfter=15)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=11, leading=16, spaceAfter=10)
    elements.append(Paragraph(basliq, title_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(metin_mezmunu, body_style))
    doc.build(elements)
    return f"PDF hesabat uğurla yaradıldı: {fayl_adi}"

@tool("Email Göndər")
def email_gonder(alici_email: str, movzu: str, mesaj_metni: str, pdf_yolu: str = None):
    """Mətn və PDF əlavə edərək e-poçt göndərir."""
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = alici_email
    msg['Subject'] = movzu
    msg.attach(MIMEText(mesaj_metni, 'plain'))
    if pdf_yolu and os.path.exists(pdf_yolu):
        with open(pdf_yolu, "rb") as f:
            pdf_attachment = MIMEApplication(f.read(), Name=os.path.basename(pdf_yolu))
            pdf_attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_yolu)}"'
            msg.attach(pdf_attachment)
    try:
        server = smtplib.SMTP('://gmail.com', 587)
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_EMAIL, alici_email, msg.as_string())
        server.quit()
        return f"E-poçt uğurla göndərildi: {alici_email}"
    except Exception as e:
        return f"E-poçt göndərmə xətası: {e}"

# ==========================================
# 3. BACARIQLI AGENTLƏRİN TƏYİNİ
# ==========================================
analitik_agent = Agent(
    role='Baş Qlobal Trend və Data Analitiki (Senior Lead)',
    goal='Yüksək CPM gətirən, yoxlanılmış maliyyə/AI mövzularını müəyyən etmək.',
    backstory='15 illik rəqəmsal marketinq və SEO təcrübəsinə malik baş analitikssən.',
    tools=[search_tool],
    verbose=True,
    llm=llm_openai # Güclü analitika üçün GPT-4o
)

yazi_agenti = Agent(
    role='Baş Redaktor və SEO Mütəxəssisi',
    goal='Google E-E-A-T qaydalarına tam uyğun peşəkar məqalələr yazmaq.',
    backstory='Nüfuzlu maliyyə jurnallarında baş redaktor işləmisən. Uzun mətndə yaradıcısan.',
    tools=[wordpress_paylas, pdf_hesabat_arat],
    verbose=True,
    llm=llm_gemini # Sizin şəkildə göndərdiyiniz Gemini modeli bura bağlandı (Uzun mətndə əladır)
)

kommunikasiya_agenti = Agent(
    role='Korporativ Əlaqələr və Dəstək Direktoru',
    goal='Biznes etikasına uyğun kommunikasiya qurmaq, bildirişlər göndərmək.',
    backstory='Müştəri təcrübəsi sahəsində 10 illik təcrübəsi olan peşəkar menecersən.',
    tools=[whatsapp_mesaj_gonder, musteriye_zeng_et, email_gonder],
    verbose=True,
    llm=llm_openai
)

trend_tapshirigi = Task(
    description='ABŞ və Avropada bu gün ən çox maraq doğuran 1 süni intellekt/maliyyə mövzusunu dərindən araşdır.',
    expected_output='Mövzu başlığı, əsas detallar və analitik xülasə.',
    agent=analitik_agent
)

yazi_tapshirigi = Task(
    description='Tapılan mövzu əsasında məqalə yaz, WordPress-ə qaralama yüklə və PDF hesabat yarat.',
    expected_output='Uğurlu WordPress və PDF yükləmə təsdiqi.',
    agent=yazi_agenti
)

ai_sistemi = Crew(
    agents=[analitik_agent, yazi_agenti, kommunikasiya_agenti],
    tasks=[trend_tapshirigi, yazi_tapshirigi],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    print("Multi-Agent Sistemi Render üzərində başladılır...")
    sonuc = ai_sistemi.kickoff()
    print("Proses uğurla tamamlandı:", sonuc)
