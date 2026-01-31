from flask import Flask, render_template, request, send_file, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from werkzeug.utils import secure_filename
import os
import threading
import time
from datetime import datetime, timedelta

try:
    import cairosvg
except ImportError:
    cairosvg = None
except Exception as e:
    print(f"⚠️ Warning: Could not load cairosvg: {e}")
    cairosvg = None

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Ensure necessary directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs('templates', exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_old_files():
    """Background task to remove files older than 1 minute."""
    while True:
        try:
            current_time = datetime.now()
            for folder in [app.config['OUTPUT_FOLDER'], app.config['UPLOAD_FOLDER']]:
                for filename in os.listdir(folder):
                    filepath = os.path.join(folder, filename)
                    if os.path.isfile(filepath):
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if current_time - file_time > timedelta(minutes=1):
                            os.remove(filepath)
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(30)

def start_cleanup_thread():
    cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
    cleanup_thread.start()

def convert_svg_to_png(svg_path):
    """Converts SVG to PNG for ReportLab compatibility."""
    png_path = os.path.join(app.config['UPLOAD_FOLDER'], f"conv_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png")
    try:
        if cairosvg:
            cairosvg.svg2png(url=svg_path, write_to=png_path)
            return png_path if os.path.exists(png_path) else None
    except Exception as e:
        print(f"SVG Conversion failed: {e}")
    return None

def create_invoice_pdf(data, logo_path, output_filename):
    """Generates a premium invoice PDF based on the Lancers Tech design."""
    width, height = A4
    c = canvas.Canvas(output_filename, pagesize=A4)
    
    # Process logo (convert SVG if needed)
    final_logo_path = None
    if logo_path and os.path.exists(logo_path):
        if logo_path.lower().endswith('.svg'):
            final_logo_path = convert_svg_to_png(logo_path)
        else:
            final_logo_path = logo_path

    # Extract Theme Colors
    primary_hex = data.get('primary_color', '#f7a80a')
    secondary_hex = data.get('secondary_color', '#2d2d2d')
    PRIMARY = colors.HexColor(primary_hex)
    SECONDARY = colors.HexColor(secondary_hex)
    BG_SECTION = colors.HexColor("#eeeeee")
    TEXT_MAIN = colors.black
    BORDER = colors.HexColor("#d1d1d1")

    # 1. TOP DECORATION
    c.setFillColor(SECONDARY)
    c.rect(0, height - 15, width * 0.7, 15, fill=1, stroke=0)
    c.setFillColor(PRIMARY)
    c.rect(width * 0.7, height - 15, width * 0.3, 15, fill=1, stroke=0)
    
    # Angular Accent
    p = c.beginPath()
    p.moveTo(width - 320, height - 15)
    p.lineTo(width, height - 15)
    p.lineTo(width, height - 45)
    p.lineTo(width - 260, height - 45)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # 2. LOGO & COMPANY HEADER
    margin_x = 40
    header_y = height - 110
    logo_w = 80
    logo_drawn = False
    
    if final_logo_path and os.path.exists(final_logo_path):
        try:
            img = ImageReader(final_logo_path)
            iw, ih = img.getSize()
            draw_h = logo_w * (ih / iw)
            c.drawImage(img, margin_x, header_y - (draw_h / 2), width=logo_w, height=draw_h, mask='auto')
            logo_drawn = True
        except: pass

    # Company Name
    text_x = margin_x + logo_w + 20 if logo_drawn else margin_x
    c.setFont("Helvetica-Bold", 32)
    full_name = data.get('company_name', 'Lancers Tech').strip()
    parts = full_name.split(' ')
    first_part = parts[0]
    rest_part = ' '.join(parts[1:]) if len(parts) > 1 else ""

    c.setFillColor(PRIMARY)
    c.drawString(text_x, header_y - 12, first_part)
    if rest_part:
        c.setFillColor(SECONDARY)
        c.drawString(text_x + c.stringWidth(first_part, "Helvetica-Bold", 32) + 12, header_y - 12, rest_part)

    # Company Details (Right-aligned)
    c.setFillColor(TEXT_MAIN)
    c.setFont("Helvetica", 9)
    info_x = width - margin_x
    c.drawRightString(info_x, header_y + 15, full_name)
    c.drawRightString(info_x, header_y + 3, data.get('company_address', ''))
    c.drawRightString(info_x, header_y - 9, data.get('company_email', ''))

    curr_y = header_y - 65

    # 3. CUSTOMER INFORMATION
    c.setFillColor(BG_SECTION)
    c.roundRect(margin_x, curr_y, 160, 24, 4, fill=1, stroke=0)
    c.setFillColor(TEXT_MAIN)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin_x + 10, curr_y + 7, "CUSTOMER INFORMATION")
    
    curr_y -= 30
    c.setFont("Helvetica-Bold", 9)
    customer_fields = [
        ("COMPANY", data.get('client_name', '')),
        ("PHONE NO", data.get('client_phone', '')),
        ("EMAIL", data.get('client_email', ''))
    ]
    
    for label, val in customer_fields:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin_x, curr_y, label)
        c.setFont("Helvetica", 9)
        c.drawString(margin_x + 90, curr_y, val)
        c.setLineWidth(0.5)
        c.setStrokeColor(SECONDARY)
        c.line(margin_x + 90, curr_y - 2, width - margin_x, curr_y - 2)
        curr_y -= 20

    curr_y -= 25

    # 4. ORDER DETAILS
    c.setFillColor(BG_SECTION)
    c.roundRect(margin_x, curr_y, 120, 24, 4, fill=1, stroke=0)
    c.setFillColor(TEXT_MAIN)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin_x + 10, curr_y + 7, "ORDER DETAILS")
    
    curr_y -= 35
    # Table Header
    c.setStrokeColor(BORDER)
    c.setFillColor(BG_SECTION)
    c.rect(margin_x, curr_y, width - (margin_x * 2), 35, fill=1, stroke=1)
    
    c.setFillColor(TEXT_MAIN)
    c.setFont("Helvetica-Bold", 8)
    table_headers = [("NO.", 55), ("ITEM DESCRIPTION", 230), ("QTY", 375), ("PRICE", 435), ("DISCOUNT", 500), ("TOTAL", 555)]
    for txt, x in table_headers:
        c.drawCentredString(x, curr_y + 12, txt)

    # Table Rows
    curr_y -= 30
    c.setFont("Helvetica", 8)
    subtotal = 0.0
    idx = 0
    while f"product_name_{idx}" in data:
        name = data.get(f"product_name_{idx}", "").strip()
        if name:
            qty = data.get(f"product_quantity_{idx}", "0")
            price = data.get(f"product_price_{idx}", "0")
            total_raw = data.get(f"product_total_{idx}", "0").replace('$', '').replace(',', '').strip()
            
            # Draw dividers
            cols_x = [40, 70, 320, 390, 440, 490, 535, 580] # Adjusted
            for i in range(len(cols_x) - 1):
                c.rect(cols_x[i], curr_y, cols_x[i+1] - cols_x[i], 30, stroke=1)
            
            c.drawCentredString(55, curr_y + 10, str(idx + 1))
            c.drawString(75, curr_y + 10, name)
            c.drawCentredString(415, curr_y + 10, qty)
            c.drawCentredString(465, curr_y + 10, f"{price} PKR")
            c.drawCentredString(512, curr_y + 10, "0 PKR")
            c.drawCentredString(557, curr_y + 10, f"{total_raw} PKR")
            
            try: subtotal += float(total_raw)
            except: pass
            
            curr_y -= 30
        idx += 1

    # Totals Table
    curr_y -= 10
    total_w = 110
    start_x = width - margin_x - total_w
    
    # GST TAX 5% row
    c.setFillColor(BG_SECTION)
    c.rect(start_x, curr_y, total_w / 2, 25, fill=1, stroke=1)
    c.rect(start_x + total_w / 2, curr_y, total_w / 2, 25, fill=1, stroke=1)
    c.setFillColor(TEXT_MAIN)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(start_x + 5, curr_y + 8, "GST TAX 5%")
    c.drawRightString(width - margin_x - 5, curr_y + 8, f"{subtotal * 0.05:,.0f} PKR")
    
    # TOTAL row
    curr_y -= 25
    c.setFillColor(BG_SECTION)
    c.rect(start_x, curr_y, total_w / 2, 25, fill=1, stroke=1)
    c.rect(start_x + total_w / 2, curr_y, total_w / 2, 25, fill=1, stroke=1)
    c.setFillColor(TEXT_MAIN)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(start_x + 10, curr_y + 8, "TOTAL")
    c.drawRightString(width - margin_x - 5, curr_y + 8, f"{subtotal * 1.05:,.0f} PKR")

    # 5. DELIVERY DETAILS
    curr_y -= 50
    c.setFillColor(BG_SECTION)
    c.roundRect(margin_x, curr_y, 110, 24, 4, fill=1, stroke=0)
    c.setFillColor(TEXT_MAIN)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin_x + 10, curr_y + 7, "DELIVERY DETAILS")
    
    curr_y -= 45
    c.setStrokeColor(SECONDARY)
    c.rect(margin_x, curr_y, 180, 20, stroke=1)
    c.rect(margin_x, curr_y - 20, 180, 20, stroke=1)
    c.line(margin_x + 80, curr_y - 20, margin_x + 80, curr_y + 20)
    
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin_x + 5, curr_y + 6, "METHOD")
    c.drawString(margin_x + 5, curr_y - 14, "DATE")
    c.setFont("Helvetica", 8)
    c.drawString(margin_x + 85, curr_y + 6, "ON-CAMPUS TRAINING")
    c.drawString(margin_x + 85, curr_y - 14, data.get('invoice_date', ''))

    # Signature
    sig_x = width - margin_x - 100
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(sig_x, curr_y, data.get('contact_person', 'CH.Shahrukh Farooq'))
    c.drawCentredString(sig_x, curr_y - 15, "C.E.O")

    # 6. FOOTER
    c.setLineWidth(0.2)
    c.setStrokeColor(SECONDARY)
    c.line(margin_x, 45, width - margin_x, 45)
    
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 30, f"📧 {data.get('company_email', '')}    |    🌐 www.lancerstech.com")
    
    c.save()
    if logo_path and logo_path.lower().endswith('.svg') and final_logo_path and os.path.exists(final_logo_path):
        try: os.remove(final_logo_path)
        except: pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-invoice', methods=['POST'])
def generate_invoice():
    logo_path = None
    try:
        if 'logo' in request.files:
            file = request.files['logo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)
                logo_path = save_path
        
        data = request.form.to_dict()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(app.config['OUTPUT_FOLDER'], f"inv_{timestamp}.pdf")
        
        create_invoice_pdf(data, logo_path, output_file)
        return send_file(output_file, as_attachment=True, download_name='invoice.pdf')
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if logo_path and os.path.exists(logo_path):
            try: os.remove(logo_path)
            except: pass

if __name__ == '__main__':
    start_cleanup_thread()
    # Use environment variable for port if available (needed for hostings like Render)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
