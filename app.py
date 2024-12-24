from flask import Flask, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os
from transformers import pipeline

# Configuration
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///incidents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24)
app.config['TEMPLATES_AUTO_RELOAD'] = True
db = SQLAlchemy(app)

# Initialize Hugging Face summarization pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# Incident Model
class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    assigned_to = db.Column(db.String(255))
    time_reported = db.Column(db.DateTime, default=datetime.utcnow)
    time_resolved = db.Column(db.DateTime)

# Load data
def load_data(filename):
    filepath = os.path.join(app.root_path, 'data', 'articles', filename)
    try:
        with open(filepath, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

SEVERITY_LEVELS = ['Critical', 'High', 'Medium', 'Low']
CATEGORY_KEYWORDS = {
    'Network': ['network', 'internet', 'server', 'connection', 'down'],
    'Hardware': ['hardware', 'device', 'machine', 'laptop', 'printer', 'broken'],
    'Software': ['software', 'app', 'program', 'crash', 'bug', 'error'],
    'Security': ['security', 'hack', 'breach', 'virus', 'malware', 'attack'],
    'Performance': ['performance', 'slow', 'lag', 'delay', 'unresponsive'],
    'Others': ['others', 'miscellaneous']
}
articles_data = load_data('incident_solutions.json')
questionnaire_data = load_data('incident_questionnaire.json')

# Helper functions
def categorize_incident(description):
    description = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in description:
                return category
    return 'Others'

def get_solutions(category):
    for item in articles_data:
        if item['category'] == category:
            return item['incidents']
    return []

def get_questionnaire(category):
    for item in questionnaire_data:
        if item.get('category') == category:
            return item.get('questions', [])
    return []

# Routes
@app.route('/', methods=['GET', 'POST'])
def home():
    form_submitted = False
    latest_incident = Incident.query.order_by(Incident.id.desc()).first()
    solutions = []

    if request.method == 'POST':
        title = request.form['incident_title']
        description = request.form['incident_description']
        severity = request.form['severity']
        assigned_to = request.form['assigned_engineer']
        status = request.form['status']

        category = categorize_incident(description)

        new_incident = Incident(
            title=title, description=description, category=category,
            severity=severity, status=status, assigned_to=assigned_to
        )
        db.session.add(new_incident)
        db.session.commit()

        form_submitted = True
        latest_incident = Incident.query.order_by(Incident.id.desc()).first()

    if latest_incident:
        solutions = get_solutions(latest_incident.category)

    return render_template('index.html', form_submitted=form_submitted, incident=latest_incident, solutions=solutions, severity_levels=SEVERITY_LEVELS)

@app.route('/update_document', methods=['GET', 'POST'])
def update_document():
    latest_incident = Incident.query.order_by(Incident.id.desc()).first()
    if not latest_incident:
        return "No incidents found. Please create one first.", 400

    questionnaire = get_questionnaire(latest_incident.category)
    if not questionnaire:
        return "No questionnaire found for this incident's category.", 400

    if request.method == 'POST':
        session['incident_id'] = latest_incident.id
        answers = [request.form.get(f"question_{i}") for i in range(len(questionnaire))]
        session['answers'] = answers
        return redirect(url_for('document_summary'))

    return render_template('update_document.html', incident=latest_incident, questionnaire=questionnaire)

@app.route('/document_summary')
def document_summary():
    incident_id = session.get('incident_id')
    answers = session.get('answers')

    if incident_id is None or answers is None:
        return "No incident or answers found. Please update the document first.", 400

    latest_incident = Incident.query.get(incident_id)
    if not latest_incident:
        return "Incident not found.", 404

    questions = get_questionnaire(latest_incident.category)
    summary = get_summary(latest_incident.category, answers)
    return render_template('document_summary.html', incident=latest_incident, summary=summary)

def get_summary(category, answers):
    summary = f"Incident Summary - {category} Category:\n"

    if category == "Network":
        summary += f"\nThe network connectivity issue was initially detected by {answers[0]}. "
        summary += f"Diagnostic tools such as {answers[1]} were used to identify the issue. "
        summary += f"Key network devices like {answers[2]} were investigated and modified to resolve the problem. "
        summary += f"The root cause of the outage was identified as {answers[4]}. "
        summary += f"The issue was resolved by {answers[5]}. "
        summary += f"The network restoration was verified by {answers[6]}. "
        summary += f"Preventive measures include {answers[7]}. "
        summary += f"The impact was {answers[8]} and the resolution was communicated to stakeholders via {answers[9]}."

    elif category == "Hardware":
        summary += f"\nThe issue involved {answers[0]} failing. Diagnostic tests confirmed the failure through {answers[1]}. "
        summary += f"Replacement steps included {answers[2]}, and the replacement hardware was tested for proper functionality. "
        summary += f"The cause of failure was identified as {answers[5]}. "
        summary += f"The total downtime was {answers[7]} with the impact being {answers[6]}. "
        summary += f"Preventive measures implemented included {answers[9]}, ensuring future hardware reliability."

    elif category == "Software":
        summary += f"\nThe software issue involved {answers[0]}, with symptoms observed as {answers[1]}. "
        summary += f"Troubleshooting steps included {answers[2]}, followed by updates or patches as {answers[3]}. "
        summary += f"The issue was identified as {answers[5]}, with impact on users as {answers[7]}. "
        summary += f"Testing confirmed resolution, and rollback measures were in place in case of failure. "
        summary += f"Preventive measures include {answers[9]} to avoid similar software issues in the future."

    elif category == "Security":
        summary += f"\nThe security incident was detected through {answers[0]}. The incident involved {answers[1]}. "
        summary += f"Containment steps included {answers[2]}, and forensic analysis was conducted to determine the scope of the incident. "
        summary += f"The vulnerabilities exploited were {answers[5]}, and patches or updates were applied as {answers[6]}. "
        summary += f"Recovery steps included {answers[7]}. The resolution was communicated to stakeholders, and future preventative measures include {answers[9]}."

    elif category == "Performance":
        summary += f"\nThe performance issue involved {answers[0]}. Monitoring tools used to diagnose it included {answers[1]}. "
        summary += f"The contributing factors were {answers[2]}. "
        summary += f"Configuration changes or upgrades implemented include {answers[3]}, with performance improvement verified by {answers[4]}. "
        summary += f"The root cause was identified as {answers[5]}, and the resolution was communicated to users. "
        summary += f"Capacity planning for future issues includes {answers[8]}."

    elif category == "Others":
        summary += f"\nThe nature of the incident was {answers[0]}. It was discovered through {answers[1]}. "
        summary += f"Immediate actions taken include {answers[2]}, and resources involved included {answers[3]}. "
        summary += f"Key challenges included {answers[4]}, with the timeline for resolution being {answers[5]}. "
        summary += f"Final resolution involved {answers[6]}, and the incident was reviewed for further improvement."

    return summarizer(summary, max_length=500, min_length=150)[0]['summary_text']

if __name__ == '__main__':
    app.run(debug=True)
