import base64, json, os, sys, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.credentials import TokenState
from google.oauth2.credentials import Credentials

# Gmail API scopes, we need to send emails only
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def auth():
    """Authenticate with Gmail API and return credentials"""
    creds = None
    
    # Check if token.json exists with stored credentials
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_info(
            json.loads(open('token.json').read())
        )
    
    # If credentials don't exist or are invalid, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return creds

def create_message(sender, to, subject, body, attachments=None):
    """Create email message with optional attachments
    
    Args:
        sender (str): Email sender
        to (str): Email recipient
        subject (str): Email subject
        body (str): Email body content
        attachments (list): Optional list of attachment file paths
        
    Returns:
        dict: Gmail API message object
    """
    # Create multipart message
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    
    # Add body to email
    message.attach(MIMEText(body))
    
    # Process attachments if provided
    if attachments:
        for file_path in attachments:
            if not os.path.isfile(file_path):
                print(f"Warning: Attachment not found - {file_path}")
                continue
                
            # Guess the content type based on the file extension
            content_type, encoding = mimetypes.guess_type(file_path)
            
            if content_type is None or encoding is not None:
                # If type cannot be guessed, use a generic type
                content_type = 'application/octet-stream'
                
            main_type, sub_type = content_type.split('/', 1)
            
            with open(file_path, 'rb') as fp:
                # Create attachment
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(fp.read())
                
                # Encode attachment in base64
                encoders.encode_base64(attachment)
                
                # Add header with the filename
                filename = os.path.basename(file_path)
                attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                message.attach(attachment)
    
    # Encode message as URL-safe base64 string
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def send_email(service, user_id, message):
    """Send email using Gmail API"""
    try:
        sent_message = service.users().messages().send(
            userId=user_id, body=message).execute()
        return sent_message
    except Exception as error:
        print(f"An error occurred: {error}")
        return None
    
def most_relevant_email_or_default(emails, keywords):
    if not emails:
        return None

    def score(email):
        prefix = email.split('@')[0].lower()
        
        # Check for exact matches
        for i, keyword in enumerate(keywords):
            if prefix == keyword:
                return i  # Score is just the index for exact match
        
        # Check for partial matches
        for i, keyword in enumerate(keywords):
            if keyword in prefix:
                return i + 0.5  # Add small penalty for partial match
        
        # No match
        return len(keywords) * 2  # Large score for no match

    return min(emails, key=score)  # Select email with lowest score


## Settings

# We are going to scrape job-related emails
priority_email_keywords = [
    "cv",
    "career",
    "job",
    "resume",
    "hr",
    "recruiting",
    "recruitment",
    "hiring",
    "hire",
    "humanresource",
    "apply",
    "application",
    "opportunities",
    "talent",
    "join",
    "employment",
    "staffing",
    "work",
    "vacancy",
    "vacancies",
    "people",
    "personnel",
    "team",

    # More generic emails but still more relevant than some random addresses
    "hello",
    "contact",
    "info",
    "general",
    "inquiry",
    "office"
]

# Email template that is used for sending emails to companies
email_subject = "Sitecore Development for {company} Performance Boost"

email_body = (
    "Hi,\n\n"
    "I'm Maksim Shamihulau, a Senior Software Developer and Tech Enthusiast "
    "with 15 years of experience specializing in web development.\n\n"
    "I noticed that {company} is interested in Sitecore/.NET. I have successfully "
    "completed 10+ Sitecore projects with various integrations for well-known enterprises "
    "such as Procter & Gamble, Sanofi, Sage, Lotus Cars, and more. With Sitecore, I have "
    "helped businesses increase web traffic, reduce bounce rates, lower solution costs, "
    "and enhance conversion rates.\n\n"
    "Additionally, I can integrate your existing services with modern technologies such as "
    ".NET, Python, Node.js, JavaScript, Vue, and React to optimize and upgrade your "
    "web development process.\n\n"
    "I would love to share some best practices and insights from my experience working with "
    "Sitecore. Let's connect - I look forward to hearing from you soon.\n\n"
    "Best regards,\n"
    "Maksim Shamihulau\n\n"
    "My LinkedIn: https://www.linkedin.com/in/maksim-shamihulau/"
    )

email_attachments = ['Resume-Maksim-Shamihulau.pdf']


## Main

# Load companies from input file
input_file = sys.argv[1] or 'companies.json'

with open(input_file, 'r') as f:
    companies = json.load(f)

if not companies:
    print(f"No companies found in the input file {input_file}")
    sys.exit(1)

# After Gmail authentication our credentials will be stored here
creds = None

for company in companies:
    emails = company.get('emails')

    # Skip if no email found
    if not emails: continue

    recipient = most_relevant_email_or_default(emails, priority_email_keywords)
    
    # Special value indicating the authenticated user to avoid emails being flagged with warning 
    sender = "me"
    to = recipient 
    subject = email_subject.format(company=company['name'])
    body = email_body.format(company=company['name'])

    # Authenticate(or get token) with Gmail API if not already
    if not creds or creds.token_state != TokenState.FRESH:
        creds = auth()
        service = build('gmail', 'v1', credentials=creds)

    email = create_message(sender, to, subject, body, email_attachments)
    result = send_email(service, 'me', email)

    if result:
        print(f"Email sent to {to} successfully.")
    else:
        print(f"An error occurred sending email to {to}.")

    # Throttle sending since Gmail has limit of 500 emails/day 
    # There are some mentions suggesting to send an email not often than every 3 min
    time.sleep(3 * 60)