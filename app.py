import os
import re
import uuid
import cv2
import pytesseract
from flask import Flask, request, render_template, jsonify, send_from_directory

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# **FIX IS HERE**: Import the text alignment constants
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import inch

# --- CONFIGURATION ---
# For Windows, if Tesseract is not in your PATH, uncomment and set the path below.
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

UPLOAD_FOLDER = 'uploads'
GENERATED_FOLDER = 'generated'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(GENERATED_FOLDER):
    os.makedirs(GENERATED_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER

# --- IMAGE & DATA PROCESSING ---

def extract_and_save_photo(image_path, output_path):
    """
    Finds and crops the beneficiary's photo from the screenshot.
    Returns True if a photo was found and saved, False otherwise.
    """
    try:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / float(h)
            if 0.7 < aspect_ratio < 1.0 and w > 100 and h > 100:
                margin = 5
                photo_crop = img[y-margin:y+h+margin, x-margin:x+w+margin]
                cv2.imwrite(output_path, photo_crop)
                return True
        return False
    except Exception as e:
        print(f"Error in photo extraction: {e}")
        return False

def extract_details_from_text(text):
    """
    Parses OCR text with a more robust and flexible extraction logic.
    """
    details = {
        "Name": "N/A", "Beneficiary ID": "N/A", "Date": "N/A", "Time": "N/A",
        "Certificate Number": "N/A", "Scheme": "N/A", "Aadhaar": "N/A",
        "Mobile No": "N/A", "Category": "N/A", "Scheme Belongs To": "N/A"
    }

    # Extract from main paragraph using regex
    match_date = re.search(r"as on\s*(\d{2}-\d{2}-\d{4})", text)
    if match_date:
        details["Date"] = match_date.group(1)

    match_time = re.search(r"as on\s*\d{2}-\d{2}-\d{4}\s*(\d{2}:\d{2}:\d{2})", text)
    if match_time:
        details["Time"] = match_time.group(1)
    
    match_bsa = re.search(r"vide BSA ID\s*(\d+)", text)
    if match_bsa:
        details["Certificate Number"] = match_bsa.group(1)

    match_name_p = re.search(r"Certified that the Beneficiary\s+(.*?)\s+having Beneficiary ID", text, re.DOTALL)
    if match_name_p:
        details["Name"] = match_name_p.group(1).strip()
    
    # Extract from the key-value list
    match_aadhaar = re.search(r"Aadhaar:\s*(\S+)", text)
    if match_aadhaar:
        details["Aadhaar"] = match_aadhaar.group(1)
        
    match_ben_id = re.search(r"Beneficiary ID:\s*(\S+)", text)
    if match_ben_id:
        details["Beneficiary ID"] = match_ben_id.group(1)

    match_name = re.search(r"Name:\s*(.*)", text)
    if match_name:
        details["Name"] = match_name.group(1).strip()
        
    match_mobile = re.search(r"Mobile No:\s*(\S+)", text)
    if match_mobile:
        details["Mobile No"] = match_mobile.group(1)

    match_cat = re.search(r"Cat/Gen:\s*(\S+)", text)
    if match_cat:
        details["Category"] = match_cat.group(1)

    match_scheme = re.search(r"Scheme:\s*(.*?)\s*Name:", text, re.DOTALL)
    if match_scheme:
        scheme_text = " ".join(match_scheme.group(1).strip().split())
        details["Scheme"] = scheme_text
        
    match_belongs_to = re.search(r"Scheme Belongs to:\s*(.*)", text, re.IGNORECASE)
    if match_belongs_to:
        details["Scheme Belongs To"] = match_belongs_to.group(1).strip()

    return details

def generate_certificate_pdf(details, photo_path, pdf_path):
    """
    Generates the final PDF with a larger font size for the entire document.
    """
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.75*inch, leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    
    # --- STYLE CUSTOMIZATIONS ---
    styles['Normal'].fontSize = 12
    styles['Normal'].leading = 15

    styles.add(ParagraphStyle(name='Justified',
                              parent=styles['Normal'],
                              alignment=TA_JUSTIFY))

    # **FIX IS HERE**: Changed font to 'Helvetica-Bold' which is a standard, safe font.
    styles.add(ParagraphStyle(name='h1_Center',
                              parent=styles['h1'],
                              fontName='Helvetica-Bold', # Changed from Times-Bold
                              fontSize=22,
                              alignment=TA_CENTER))

    story = []

    # --- HEADER AND TITLE ---
    header_text = "CENTRAL Govt - National Social Assistance Programme (NSAP)"
    story.append(Paragraph(header_text, styles['Normal']))
    
    story.append(Spacer(1, 0.1 * inch))
    
    title_text = "LIFE CERTIFICATE"
    story.append(Paragraph(title_text, styles['h1_Center'])) 
    story.append(Spacer(1, 0.25 * inch))
    
    # --- INTRODUCTORY PARAGRAPH ---
    intro_text = (f"Certified that the Beneficiary <b>{details.get('Name', 'N/A')}</b> having Beneficiary ID - "
                  f"<b>{details.get('Beneficiary ID', 'N/A')}</b> has been biometrically authenticated his/her presence "
                  f"and that he/she is alive as on - <b>{details.get('Date', 'N/A')} {details.get('Time', 'N/A')}</b> "
                  f"vide BSA ID - <b>{details.get('Certificate Number', 'N/A')}</b>.")
    story.append(Paragraph(intro_text, styles['Justified']))
    story.append(Spacer(1, 0.25 * inch))

    # --- PHOTO ---
    if photo_path and os.path.exists(photo_path):
        img = Image(photo_path, width=1.5*inch, height=1.9*inch)
        img.hAlign = 'LEFT'
        story.append(img)
        story.append(Spacer(1, 0.25 * inch))

    # --- BENEFICIARY DETAILS TABLE ---
    table_data = [
        ['Aadhaar Number (Masked)', Paragraph(details.get('Aadhaar', 'N/A'), styles['Normal'])],
        ['Beneficiary ID',        Paragraph(details.get('Beneficiary ID', 'N/A'), styles['Normal'])],
        ['Scheme Name',           Paragraph(details.get('Scheme', 'N/A'), styles['Normal'])],
        ['Beneficiary Name',      Paragraph(details.get('Name', 'N/A'), styles['Normal'])],
        ['Mobile Number (Masked)',Paragraph(details.get('Mobile No', 'N/A'), styles['Normal'])],
        ['Category / Gender',     Paragraph(details.get('Category', 'N/A'), styles['Normal'])],
        ['(Scheme Belongs To:)',  Paragraph(details.get('Scheme Belongs To', 'N/A'), styles['Normal'])],
    ]
    
    table = Table(table_data, colWidths=[2.5 * inch, 4.5 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#4F81BD')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), 
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)

    # Build the PDF
    doc.build(story)

# --- FLASK ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
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

        # --- Process Image ---
        photo_filename = f"photo_{unique_id}.jpg"
        photo_path = os.path.join(app.config['GENERATED_FOLDER'], photo_filename)
        photo_found = extract_and_save_photo(image_path, photo_path)
        
        extracted_text = pytesseract.image_to_string(image_path)
        beneficiary_details = extract_details_from_text(extracted_text)

        # --- Generate PDF ---
        pdf_filename = f"LifeCertificate-{unique_id}.pdf"
        pdf_path = os.path.join(app.config['GENERATED_FOLDER'], pdf_filename)
        generate_certificate_pdf(beneficiary_details, photo_path if photo_found else None, pdf_path)
        
        # --- Clean up temporary files ---
        os.remove(image_path)
        if photo_found:
            os.remove(photo_path)

        return jsonify({"pdf_filename": pdf_filename})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['GENERATED_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)