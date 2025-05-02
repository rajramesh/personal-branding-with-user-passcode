import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io
import base64
import json
import docx
import PyPDF2
import tempfile
from supabase import create_client, Client

# Initialize session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'initial_context' not in st.session_state:
    st.session_state.initial_context = ""
if 'resume_file' not in st.session_state:
    st.session_state.resume_file = None
if 'questions_data' not in st.session_state:
    st.session_state.questions_data = None
if 'responses' not in st.session_state:
    st.session_state.responses = []
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0
if 'max_question_viewed' not in st.session_state:
    st.session_state.max_question_viewed = 0
if 'login_error' not in st.session_state:
    st.session_state.login_error = None

def extract_text_from_pdf(file_path):
    """Extract text from a PDF file."""
    pdf_reader = PyPDF2.PdfReader(file_path)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_path):
    """Extract text from a DOCX file."""
    doc = docx.Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_txt(file):
    """Extract text from a TXT file."""
    return file.getvalue().decode('utf-8')

def process_uploaded_files(files):
    """Process all uploaded files and extract their content."""
    extracted_texts = []
    for file in files:
        # Create a temporary file to handle the uploaded file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(file.getvalue())
            tmp_file_path = tmp_file.name

        try:
            if file.type == "application/pdf":
                text = extract_text_from_pdf(tmp_file_path)
            elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                text = extract_text_from_docx(tmp_file_path)
            elif file.type == "text/plain":
                text = extract_text_from_txt(file)
            else:
                text = f"Unsupported file type: {file.type}"
            
            extracted_texts.append({
                "filename": file.name,
                "content": text
            })
        finally:
            # Clean up the temporary file
            os.unlink(tmp_file_path)
    
    return extracted_texts

# Set page config must be the first Streamlit command
st.set_page_config(page_title="Personal Brand Discovery", layout="centered")

# Load environment variables
load_dotenv()

# Initialize Supabase client
def init_supabase() -> Client:
    """Initialize Supabase client with credentials from environment variables."""
    supabase_url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        st.error("""
            Please set up your Supabase credentials:
            - For local development: Add them to your .env file
            - For Streamlit Cloud: Add them to your app secrets
            """)
        st.stop()
    
    return create_client(supabase_url, supabase_key)

supabase = init_supabase()

def handle_login():
    if st.session_state.login_email and st.session_state.login_password:
        try:
            response = supabase.auth.sign_in_with_password({
                "email": st.session_state.login_email,
                "password": st.session_state.login_password
            })
            if response.user:
                st.session_state.logged_in = True
                st.session_state.user = response.user
                st.session_state.login_error = None
        except Exception as e:
            st.session_state.login_error = str(e)
    else:
        st.session_state.login_error = "Please fill in all fields"

def create_pdf(result, responses, questions_data, similar_figures):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        textColor=colors.HexColor('#2E4053')
    )
    
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        textColor=colors.HexColor('#2E4053')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        leading=14
    )
    
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#2E4053')
    )
    
    # Build PDF content
    content = []
    
    # Add title
    content.append(Paragraph("Personal Brand Analysis", title_style))
    content.append(Spacer(1, 20))
    
    # Add initial context section
    content.append(Paragraph("Initial Context", section_title_style))
    content.append(Paragraph(st.session_state.initial_context, body_style))
    content.append(Spacer(1, 20))
    
    # Add analysis section
    content.append(Paragraph("Analysis", section_title_style))
    
    # Split the result into sections based on numbered points
    sections = result.split('\n\n')
    for section in sections:
        if section.strip():
            # Check if it's a numbered section
            if section.strip()[0].isdigit():
                # Extract the section title and content
                parts = section.split('.', 1)
                if len(parts) > 1:
                    section_title = parts[0].strip() + '.'
                    section_content = parts[1].strip()
                    # First line: section number and title
                    content.append(Paragraph(section_title, bold_style))
                    # Second line: content
                    content.append(Paragraph(section_content, body_style))
                else:
                    content.append(Paragraph(section, body_style))
            else:
                content.append(Paragraph(section, body_style))
            content.append(Spacer(1, 12))
    
    # Add similar personal brands section
    content.append(Paragraph("Notable People with Similar Personal Brands", section_title_style))
    content.append(Paragraph(similar_figures, body_style))
    content.append(Spacer(1, 20))
    
    content.append(PageBreak())
    
    # Add questions and responses section
    content.append(Paragraph("Your Responses", section_title_style))
    content.append(Spacer(1, 15))
    
    for i, (q, r) in enumerate(zip(questions_data, responses), 1):
        if r.strip():  # Only include answered questions
            content.append(Paragraph(f"Question {i}: {q['question']}", bold_style))
            if q.get('description'):
                content.append(Paragraph(q['description'], body_style))
            content.append(Paragraph(r, body_style))
            content.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(content)
    return buffer.getvalue()

# Main application logic
def main():
    st.title("Personal Brand Discovery")
    
    # Authentication UI
    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.header("Login")
            st.text_input("Email", key="login_email")
            st.text_input("Password", type="password", key="login_password")
            st.button("Login", on_click=handle_login)
            
            if st.session_state.login_error:
                st.error(st.session_state.login_error)
        
        with tab2:
            st.header("Register")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            if st.button("Register"):
                try:
                    response = supabase.auth.sign_up({
                        "email": reg_email,
                        "password": reg_password
                    })
                    if response.user:
                        st.success("Registration successful! Please log in.")
                except Exception as e:
                    st.error(f"Error during registration: {str(e)}")
        
        return  # Stop here if not logged in

    # Show logout button in sidebar when logged in
    with st.sidebar:
        st.write(f"Logged in as: {st.session_state.user.email}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.login_error = None
            st.experimental_rerun()

    # Load OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY not found in environment variables")
        st.stop()

    client = OpenAI(api_key=api_key)

    # Load initial context gathering instructions
    try:
        with open("initial_context_gathering.txt", "r") as file:
            context_instructions = file.read()
    except FileNotFoundError:
        st.error("Initial context gathering instructions file not found. Please contact support.")
        st.stop()
    
    # Initial context gathering
    st.markdown(context_instructions)
    
    with st.form("initial_context_form"):
        # Add name field
        user_name = st.text_input(
            "What's your name?",
            value=st.session_state.user_name,
            placeholder="Enter your name"
        )
        
        initial_context = st.text_area(
            "Share your information here:",
            height=500,
            value=st.session_state.initial_context
        )
        
        # Add file uploader for multiple documents
        st.write("Please upload any relevant documents (PDF, DOCX, or TXT format) such as your resume, personal statements, career goals, or other materials that can help us understand your professional journey.")
        uploaded_files = st.file_uploader(
            "Upload Files", 
            type=['pdf', 'docx', 'txt'], 
            key="file_uploader",
            accept_multiple_files=True
        )
        
        initial_submitted = st.form_submit_button("Submit Initial Information")
    
    if initial_submitted:
        if not user_name:
            st.error("Please provide your name.")
            st.stop()
        if not initial_context:
            st.error("Please provide some information about yourself and your goals.")
            st.stop()
        
        # Store the initial context, name, and uploaded files in session state
        st.session_state.user_name = user_name
        st.session_state.initial_context = initial_context
        st.session_state.uploaded_files = uploaded_files
        
        with st.spinner("Analyzing your context to determine relevant questions..."):
            try:
                # Process uploaded files and extract their content
                if uploaded_files:
                    extracted_docs = process_uploaded_files(uploaded_files)
                    # Add document content to the context
                    full_context = initial_context + "\n\nAdditional information from uploaded documents:\n"
                    for doc in extracted_docs:
                        full_context += f"\nContent from {doc['filename']}:\n{doc['content']}\n"
                else:
                    full_context = initial_context
                
                # Generate questions based on context
                system_prompt = """You are a personal brand development expert. Based on the user's context and any uploaded documents, generate a set of relevant questions that will help them develop their personal brand. 
                The questions should be specific to their situation and goals. Format the response as a JSON array of objects, where each object has 'question' and 'description' fields.
                The questions should be thought-provoking and help uncover their unique value proposition, strengths, and professional identity.
                DO NOT ask questions about information that is already provided in the uploaded documents."""
                
                chat_response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_context}
                    ],
                    temperature=0.7
                )
                
                # Parse the generated questions and store in session state
                st.session_state.questions_data = json.loads(chat_response.choices[0].message.content)
                st.session_state.responses = [""] * len(st.session_state.questions_data)
            except Exception as e:
                st.error("An error occurred while generating questions. Please try again.")
                st.exception(e)
                st.stop()
    
    # Show questions form if we have questions data
    if st.session_state.questions_data:
        total_questions = len(st.session_state.questions_data)
        unanswered_questions = sum(1 for r in st.session_state.responses if not r.strip())
        
        # Add CSS to hide the submit button
        st.markdown("""
            <style>
            .stHidden {
                display: none;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Update max question viewed
        st.session_state.max_question_viewed = max(st.session_state.max_question_viewed, st.session_state.current_question)
        
        # Display progress
        st.progress((total_questions - unanswered_questions) / total_questions)
        st.write(f"Questions remaining: {unanswered_questions} out of {total_questions}")
        
        # Navigation buttons
        col1, col2 = st.columns(2)
        
        # Only show navigation buttons if they are applicable
        if st.session_state.current_question > 0:
            with col1:
                if st.button("Previous Question"):
                    st.session_state.current_question -= 1
        
        if st.session_state.current_question < total_questions - 1:
            with col2:
                if st.button("Next Question"):
                    st.session_state.current_question += 1
        
        # Display current question
        with st.form("personal_brand_form"):
            q = st.session_state.questions_data[st.session_state.current_question]
            st.subheader(f"Question {st.session_state.current_question + 1} of {total_questions}")
            st.subheader(q['question'])
            if q.get('description'):
                st.markdown(q['description'])
            response = st.text_area(
                "Your response:",
                height=100,
                key=f"response_{st.session_state.current_question}",
                value=st.session_state.responses[st.session_state.current_question]
            )
            st.session_state.responses[st.session_state.current_question] = response
            
            # Always show a submit button, but change the label based on position
            if st.session_state.current_question == total_questions - 1:
                submitted = st.form_submit_button("Submit Your Responses")
            else:
                st.write("*Please use the 'Next Question' button above to continue*")
                submitted = st.form_submit_button("Submit for Analysis Now (Not Preferred)")

        if submitted:
            with st.spinner("Analyzing your responses..."):
                try:
                    # Load analysis prompt template
                    try:
                        with open("analysis_prompt.txt", "r") as file:
                            analysis_prompt_template = file.read()
                    except FileNotFoundError:
                        st.error("Analysis prompt template file not found. Please contact support.")
                        st.stop()

                    # Build the responses section
                    responses_section = ""
                    for i, (q, r) in enumerate(zip(st.session_state.questions_data, st.session_state.responses), 1):
                        if r.strip():  # Only include non-empty responses
                            responses_section += f"\nQuestion {i}: {q['question']}\nResponse: {r}\n"

                    # Format the analysis prompt
                    analysis_prompt = analysis_prompt_template.format(
                        user_name=st.session_state.user_name,
                        initial_context=st.session_state.initial_context,
                        responses=responses_section
                    )
                    
                    analysis_response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a personal brand development expert. Provide detailed, actionable insights based on the available information. If some questions were not answered, focus on the information provided in the initial context and answered questions."},
                            {"role": "user", "content": analysis_prompt}
                        ],
                        temperature=0.7
                    )
                    
                    st.session_state.analysis_result = analysis_response.choices[0].message.content
                    st.success("Here is your personal brand insight:")
                    st.write(st.session_state.analysis_result)

                    # Find similar personal brands
                    st.markdown("---")
                    st.subheader("Notable People with Similar Personal Brands")
                    
                    with st.spinner("Finding notable people with similar personal brands..."):
                        # First, get a concise summary of the personal brand
                        brand_summary_response = client.chat.completions.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "Extract the key characteristics and essence of this person's personal brand in a concise way that can be used for searching similar notable figures. Focus on their unique qualities, values, and impact."},
                                {"role": "user", "content": st.session_state.analysis_result}
                            ],
                            temperature=0.7
                        )
                        
                        brand_summary = brand_summary_response.choices[0].message.content
                        
                        # Search for similar notable figures
                        search_query = f"notable successful famous people who exemplify {brand_summary}"
                        search_results = client.chat.completions.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "You are tasked with identifying 3 notable and positively regarded historical or contemporary figures who share similar personal brand characteristics. Focus on positive role models and avoid controversial or infamous figures. For each person, provide their name and a brief explanation of how their personal brand aligns with the given characteristics."},
                                {"role": "user", "content": f"Find 3 notable figures who share these brand characteristics: {brand_summary}"}
                            ],
                            temperature=0.7
                        )
                        
                        similar_figures = search_results.choices[0].message.content
                        st.write(similar_figures)

                    # PDF Download functionality
                    st.markdown("---")
                    st.subheader("Download Your Results")
                    
                    # Create PDF
                    pdf_data = create_pdf(st.session_state.analysis_result, st.session_state.responses, st.session_state.questions_data, similar_figures)
                    
                    # Create download button with personalized filename
                    b64 = base64.b64encode(pdf_data).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{st.session_state.user_name}-personal-brand-analysis.pdf">📥 Download PDF Report</a>'
                    st.markdown(href, unsafe_allow_html=True)

                except Exception as e:
                    st.error("An error occurred while generating the analysis. Please try again.")
                    st.exception(e)

if __name__ == "__main__":
    main()
