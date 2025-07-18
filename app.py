import os
import re
import uuid
import cv2
import pytesseract
import traceback # Import the traceback module
from flask import Flask, request, render_template, jsonify, send_from_directory

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import inch

# --- CONFIGURATION ---
UPLOAD_FOLDER = 'uploads'
GENERATED_FOLDER = 'generated'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(GENERATED_FOLDER):
    os.makedirs(GENERATED_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER

# --- DATA & PDF FUNCTIONS (No changes here) ---

def extract_details_from_text(text):
    details = {
        "Name": "N/A", "Beneficiary ID": "N/A", "Date": "N/A", "Time": "N/A",
        "Certificate Number": "N/A", "Scheme": "N/A", "Aadhaar": "N/A",
        "Mobile No": "N/A", "Category": "N/A", "Scheme Belongs To": "N/A"
    }
    match_date = re.search(r"as on\s*(\d{2}-\d{2}-\d{4})", text)
    if match_date: details["Date"] = match_date.group(1)
    match_time = re.search(r"as on\s*\d{2}-\d{2}-\d{4}\s*(\d{2}:\d{2}:\d{2})", text)
    if match_time: details["Time"] = match_time.group(1)
    match_bsa = re.search(r"vide BSA ID\s*(\d+)", text)
    if match_bsa: details["Certificate Number"] = match_bsa.group(1)
    match_name_p = re.search(r"Certified that the Beneficiary\s+(.*?)\s+having Beneficiary ID", text, re.DOTALL)
    if match_name_p: details["Name"] = match_name_p.group(1).strip()
    match_aadhaar = re.search(r"Aadhaar:\s*(\S+)", text)
    if match_aadhaar: details["Aadhaar"] = match_aadhaar.group(1)
    match_ben_id = re.search(r"Beneficiary ID:\s*(\S+)", text)
    if match_ben_id: details["Beneficiary ID"] = match_ben_id.group(1)
    match_name = re.search(r"Name:\s*(.*)", text)
    if match_name: details["Name"] = match_name.group(1).strip()
    match_mobile = re.search(r"Mobile No:\s*(\S+)", text)
    if match_mobile: details["Mobile No"] = match_mobile.group(1)
    match_cat = re.search(r"Cat/Gen:\s*(\S+)", text)
    if match_cat: details["Category"] = match_cat.group(1)
    match_scheme = re.search(r"Scheme:\s*(.*?)\s*Name:", text, re.DOTALL)
    if match_scheme:
        details["Scheme"] = " ".join(match_scheme.group(1).strip().split())
    match_belongs_to = re.search(r"Scheme Belongs to:\s*(.*)", text, re.IGNORECASE)
    if match_belongs_to: details["Scheme Belongs To"] = match_belongs_to.group(1).strip()
    return details

def generate_certificate_pdf(details, pdf_path):
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.75*inch, leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    styles['Normal'].fontSize = 12
    styles['Normal'].leading = 15
    styles.add(ParagraphStyle(name='Justified', parent=styles['Normal'], alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='h1_Center', parent=styles['h1'], fontName='Helvetica-Bold', fontSize=22, alignment=TA_CENTER))
    story = []
    header_text = "CENTRAL Govt - National Social Assistance Programme (NSAP)"
    story.append(Paragraph(header_text, styles['Normal']))
    story.append(Spacer(1, 0.1 * inch))
    title_text = "LIFE CERTIFICATE"
    story.append(Paragraph(title_text, styles['h1_Center'])) 
    story.append(Spacer(1, 0.25 * inch))
    intro_text = (f"Certified that the Beneficiary <b>{details.get('Name', 'N/A')}</b> having Beneficiary ID - "
                  f"<b>{details.get('Beneficiary ID', 'N/A')}</b> has been biometrically authenticated his/her presence "
                  f"and that he/she is alive as on - <b>{details.get('Date', 'N/A')} {details.get('Time', 'N/A')}</b> "
                  f"vide BSA ID - <b>{details.get('Certificate Number', 'N/A')}</b>.")
    story.append(Paragraph(intro_text, styles['Justified']))
    story.append(Spacer(1, 0.25 * inch))
    table_data = [['Aadhaar Number (Masked)', Paragraph(details.get('Aadhaar', 'N/A'), styles['Normal'])],
                  ['Beneficiary ID', Paragraph(details.get('Beneficiary ID', 'N/A'), styles['Normal'])],
                  ['Scheme Name', Paragraph(details.get('Scheme', 'N/A'), styles['Normal'])],
                  ['Beneficiary Name', Paragraph(details.get('Name', 'N/A'), styles['Normal'])],
                  ['Mobile Number (Masked)',Paragraph(details.get('Mobile No', 'N/A'), styles['Normal'])],
                  ['Category / Gender', Paragraph(details.get('Category', 'N/A'), styles['Normal'])],
                  ['(Scheme Belongs To:)', Paragraph(details.get('Scheme Belongs To', 'N/A'), styles['Normal'])],]
    table = Table(table_data, colWidths=[2.5 * inch, 4.5 * inch])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#4F81BD')),('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), 
        ('FONTSIZE', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 12), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(table)
    doc.build(story)

# --- FLASK ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # **FIX IS HERE**: Added a master error-catching block
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        if file:
            unique_id = str(uuid.uuid4())
            filename = unique_id + os.path.splitext(file.filename)[1]
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(image_path)
            
            extracted_text = pytesseract.image_to_string(image_path)
            beneficiary_details = extract_details_from_text(extracted_text)

            pdf_filename = f"LifeCertificate-{unique_id}.pdf"
            pdf_path = os.path.join(app.config['GENERATED_FOLDER'], pdf_filename)
            # Temporarily removed photo extraction to simplify
            generate_certificate_pdf(beneficiary_details, pdf_path)
            
            os.remove(image_path)

            return jsonify({"pdf_filename": pdf_filename})

    except Exception as e:
        # This will force the error to be printed to the logs
        print("--- AN ERROR OCCURRED IN THE UPLOAD ROUTE ---")
        traceback.print_exc()
        print("---------------------------------------------")
        return jsonify({"error": "A critical server error occurred."}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['GENERATED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)