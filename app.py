from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import subprocess
import os
import json
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import logging
from uuid import uuid4
from urllib.parse import urlparse

app = Flask(__name__)

# Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///audit_history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database Model
class AuditHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    performance_score = db.Column(db.Float)
    seo_title = db.Column(db.String(200))
    seo_meta_description = db.Column(db.String(1000))
    accessibility_issues = db.Column(db.Integer)
    report_path = db.Column(db.String(200))


# Helper function: Validate URL
def validate_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and parsed.netloc

# Helper function: Performance Audit
def audit_performance(url):
    """
    Perform a performance audit using Lighthouse and calculate key metrics.
    """
    report_file = "lighthouse_report.json"
    try:
        # Run Lighthouse for performance metrics
        command = [
            "lighthouse", url, "--output=json", 
            f"--output-path={report_file}", "--quiet"
        ]
        subprocess.run(command, check=True)

        # Read and parse the Lighthouse report
        with open(report_file, "r") as file:
            data = json.load(file)

        metrics = {
            "performance_score": data["categories"]["performance"]["score"] * 100,
            "first_contentful_paint": data["audits"]["first-contentful-paint"]["displayValue"],
            "speed_index": data["audits"]["speed-index"]["displayValue"],
            "largest_contentful_paint": data["audits"]["largest-contentful-paint"]["displayValue"],
            "time_to_interactive": data["audits"]["interactive"]["displayValue"],
            "total_blocking_time": data["audits"]["total-blocking-time"]["displayValue"]
        }

        os.remove(report_file)  # Clean up the report file
        return metrics
    except Exception as e:
        logging.error(f"Performance audit failed: {e}")
        return {
            "performance_score": 0,
            "first_contentful_paint": None,
            "speed_index": None,
            "largest_contentful_paint": None,
            "time_to_interactive": None,
            "total_blocking_time": None
        }

# Helper function: SEO Audit
def audit_seo(url):
    """
    Perform an SEO audit by analyzing HTML metadata and content structure.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.title.string.strip() if soup.title else "N/A"
        meta_description = soup.find("meta", attrs={"name": "description"})
        description_content = meta_description["content"].strip() if meta_description else "N/A"

        h1_tags = [h1.get_text().strip() for h1 in soup.find_all("h1")]
        h2_tags = [h2.get_text().strip() for h2 in soup.find_all("h2")]

        # Check for duplicate titles or meta descriptions
        canonical = soup.find("link", attrs={"rel": "canonical"})
        canonical_url = canonical["href"] if canonical else "N/A"

        return {
            "seo_title": title,
            "seo_meta_description": description_content,
            "h1_tags": h1_tags,
            "h2_tags": h2_tags,
            "canonical_url": canonical_url
        }
    except Exception as e:
        logging.error(f"SEO audit failed: {e}")
        return {
            "seo_title": None,
            "seo_meta_description": None,
            "h1_tags": None,
            "h2_tags": None,
            "canonical_url": None
        }


def audit_accessibility(url):
    """
    Perform an accessibility audit to identify potential issues:
    - Missing ARIA roles
    - Missing or skipped headers
    - Images without alt attributes
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Check for missing ARIA roles
        missing_aria_roles = len([el for el in soup.find_all() if not el.get("role")])

        # 2. Check for missing or skipped headers
        headers = [h.name for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]
        header_issues = 0
        if headers:
            expected_level = 1
            for header in headers:
                current_level = int(header[1])  # Extract header level (e.g., '1' from 'h1')
                if current_level > expected_level + 1:
                    header_issues += 1
                expected_level = current_level

        # 3. Check for missing alt attributes in images
        missing_alt = len([img for img in soup.find_all("img") if not img.get("alt")])

        # Aggregate results
        return {
            "missing_aria_roles": missing_aria_roles,
            "header_issues": header_issues,
            "missing_alt_attributes": missing_alt,
            "accessibility_issues": missing_aria_roles + header_issues + missing_alt,
        }
    except Exception as e:
        logging.error(f"Accessibility audit failed: {e}")
        return {
            "missing_aria_roles": None,
            "header_issues": None,
            "missing_alt_attributes": None,
            "accessibility_issues": 0,  # Return 0 issues if the audit fails
        }


# New pdf file code 28/12/2024
def generate_pdf_report(url, performance_metrics, seo_metrics, accessibility_metrics):
    domain_name = url.replace('https://', '').replace('http://', '').replace('www.', '').split('.')[0].capitalize()
    
    class PDF(FPDF):
        # Header for each page
        def header(self):
            if self.page_no() == 1:
                self.set_font("Times", "B", 18)
                self.cell(0, 10, f"Website Audit Report for {domain_name} by WebOptimizer", border=0, ln=1, align="C")
                self.ln(5)

                # Add metrics glory inf
                self.set_text_color(0, 0, 255)  # Set text color to blue for the hyperlink
                self.set_font("Times", "B", 14)  # Underline the hyperlink
                self.cell(0, 10, "Click me for the meanings of the metrics in this report", border=0, ln=1, align="C", link="http://127.0.0.1:5000/metrics_glossary")
                self.ln(5)

        # Footer for each page
        def footer(self):
            self.set_y(-15)
            self.set_font("Times", "I", 8)

            # Create the full text "WebOptimizer | Page X"
            weboptimizer = 'WebOptimizer'
            full_footer_text = f"{weboptimizer} | Page {self.page_no()}"

            # Calculate the width of the full text
            text_width = self.get_string_width(full_footer_text)

            # Center the full text
            self.set_x((210 - text_width) / 2)  # Assuming A4 width (210mm)

            # Add the clickable link for "WebOptimizer" and page number
            self.set_text_color(0, 0, 255)  # Set text color to blue for the hyperlink
            self.cell(self.get_string_width(weboptimizer), 10, weboptimizer, link="http://127.0.0.1:5000/audit")
    
            self.set_text_color(0, 0, 0)  # Reset text color to black
            self.cell(self.get_string_width(f" | Page {self.page_no()}"), 10, f" | Page {self.page_no()}", ln=0)


    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Times", size=12)
    
    # Add URL Section
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 10, "Website Details:", ln=True)
    pdf.set_font("Times", size=12)
    pdf.cell(0, 10, f"URL: {url}", ln=True)
    pdf.ln(5)
    
    # Add Performance Metrics
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 10, "Performance Metrics:", ln=True)
    pdf.set_font("Times", size=12)
    for key, value in performance_metrics.items():
        pdf.multi_cell(0, 10, f"{key.replace('_', ' ').title()}: {value}")
    pdf.ln(5)
    
    # Add SEO Metrics
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 10, "SEO Metrics:", ln=True)
    pdf.set_font("Times", size=12)
    # Add static text
    pdf.multi_cell(0, 10, "SEO metrics are good in this era.")
    for key, value in seo_metrics.items():
        pdf.multi_cell(0, 10, f"{key.replace('_', ' ').title()}: {value}")
    pdf.ln(5)
    
    # Add Accessibility Metrics
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 10, "Accessibility Metrics:", ln=True)
    pdf.set_font("Times", size=12)
    for key, value in accessibility_metrics.items():
        pdf.multi_cell(0, 10, f"{key.replace('_', ' ').title()}: {value}")
    pdf.ln(5)

    # Add metrics glory inf
    pdf.set_text_color(0, 0, 255)  # Set text color to blue for the hyperlink
    pdf.set_font("Times", "B", 14)  # Underline the hyperlink
    pdf.cell(0, 10, "Click me for the meanings of the metrics in this report.", border=0, ln=1, link="http://127.0.0.1:5000/metrics_glossary")
    pdf.ln(5)
    
    # Save the PDF
    report_path = f"static/reports/Audit_Report_for_{domain_name}_by_WebOptimizer.pdf"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    pdf.output(report_path)
    
    return report_path


@app.route('/')
def index():
    return render_template('index.html')

# new audit route
@app.route('/audit', methods=['GET', 'POST'])
def audit():
    if request.method == 'POST':
        url = request.form.get('url')
        if not url or not validate_url(url):
            return render_template("audit.html", error="A valid URL is required")

        # Perform audits
        performance_metrics = audit_performance(url)
        seo_metrics = audit_seo(url)
        accessibility_metrics = audit_accessibility(url)

        # Generate PDF report
        report_path = generate_pdf_report(url, performance_metrics, seo_metrics, accessibility_metrics)

        # Save to database
        audit_entry = AuditHistory(
            url=url,
            performance_score=performance_metrics["performance_score"],
            seo_title=seo_metrics["seo_title"],
            seo_meta_description=seo_metrics["seo_meta_description"],
            accessibility_issues=accessibility_metrics["accessibility_issues"],
            report_path=report_path
        )
        db.session.add(audit_entry)
        db.session.commit()

        return render_template(
            "audit.html",
            performance_metrics=performance_metrics,
            seo_metrics=seo_metrics,
            accessibility_metrics=accessibility_metrics,
            report_url=url_for('download_report', filename=os.path.basename(report_path))
)


    return render_template("audit.html")

@app.route('/history', methods=['GET'])
def history():
    audits = AuditHistory.query.order_by(AuditHistory.id.desc()).all()
    return render_template(
        "history.html",
        audits=audits,
        get_report_url=lambda audit: url_for('download_report', filename=os.path.basename(audit.report_path))
    )


# PDF Download
@app.route('/download/<path:filename>')
def download_report(filename):
    """Serve the PDF report for download."""
    directory = os.path.join(app.root_path, 'static', 'reports')  # Ensure the directory matches where PDFs are saved
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/accessibility_check')
def accessibility_check():
    return render_template('accessibility_check.html')

@app.route('/performance_audit')
def performance_audit():
    return render_template('performance_audit.html')

@app.route('/seo_analysis')
def seo_analysis():
    return render_template('seo_analysis.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/testimonial')
def testimonial():
    return render_template('testimonial.html')

@app.route('/404')
def error():
    return render_template('404.html')
@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms_conditions')
def terms_conditions():
    return render_template('terms_conditions.html')

@app.route('/metrics_glossary')
def metrics_glossary():
    return render_template('metrics_glossary.html')

@app.route('/authentication_form')
def authentication_form():
    return render_template('authentication_form.html')

if __name__ == '__main__':
    # Initialize database
    with app.app_context():
        db.create_all()
    app.run(debug=True)