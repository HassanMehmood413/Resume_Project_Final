# backend/routes/resume.py
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
import requests
import os
import subprocess
import logging
from database import db
import json
import re

get_db = db.get_db

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

class ProfileLinks(BaseModel):
    github: str
    linkedin: str

def get_serper_enhanced_content(content, content_type):
    headers = {
        'X': '',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""Format this {content_type} information into professional resume content following this style:
    - Use action verbs and quantifiable achievements
    - Be concise but impactful
    - Focus on key accomplishments and skills
    - Make it relevant for job applications
    
    Original content: {content}"""
    
    try:
        response = requests.post(
            'https://google.serper.dev/search',
            headers=headers,
            json={'q': prompt}
        )
        if response.status_code == 200:
            return response.json()['organic'][0]['snippet']
        return content
    except Exception as e:
        logger.error(f"error: {str(e)}")
        return content

def fetch_github_data(github_url):
    try:
        headers = {
            'Authorization': '',
            'Accept': 'application/vnd.github.v3+json'
        }
        username = github_url.split('/')[-1]
        logger.debug(f"Fetching GitHub data for user: {username}")
        
        # Fetch user data
        user_response = requests.get(f'https://api.github.com/users/{username}', headers=headers)
        if user_response.status_code != 200:
            logger.error(f"GitHub API user error: {user_response.text}")
            raise HTTPException(status_code=500, detail="Failed to fetch GitHub user data")
        user_data = user_response.json()
        logger.debug(f"User Data:\n{json.dumps(user_data, indent=2)}")
        
        # Fetch repositories
        repos_response = requests.get(f'https://api.github.com/users/{username}/repos', headers=headers)
        if repos_response.status_code != 200:
            logger.error(f"GitHub API repos error: {repos_response.text}")
            raise HTTPException(status_code=500, detail="Failed to fetch GitHub repos")
        
        repos = repos_response.json()
        logger.debug(f"Found {len(repos)} repositories")
        
        # Process repositories for projects and experience
        projects = []
        experience = []
        all_languages = set()
        
        for repo in sorted(repos, key=lambda x: (x.get('stargazers_count', 0), x.get('forks_count', 0)), reverse=True):
            if not repo.get('fork'):
                logger.debug(f"\nProcessing repository: {repo['name']}")
                
                # Get languages
                lang_response = requests.get(repo['languages_url'], headers=headers)
                languages = list(lang_response.json().keys()) if lang_response.status_code == 200 else []
                all_languages.update(languages)
                
                # Get commit count
                commits_url = repo['commits_url'].split('{')[0]
                commits_response = requests.get(commits_url, headers=headers)
                commits = commits_response.json() if commits_response.status_code == 200 else []
                commit_count = len(commits)
                
                # Use actual repository description and stats
                description = (
                    f"{repo.get('description', 'A project')}. "
                    f"Technologies: {', '.join(languages)}. "
                    f"Made {commit_count} commits. "
                    f"Stars: {repo['stargazers_count']}, Forks: {repo.get('forks_count', 0)}"
                )
                
                # Add to projects if it's a significant project
                if len(projects) < 3 and (repo['stargazers_count'] > 0 or commit_count > 10):
                    project_data = {
                        'name': repo['name'],
                        'description': description,
                        'languages': languages,
                        'stars': repo['stargazers_count'],
                        'commits': commit_count,
                        'url': repo['html_url']
                    }
                    projects.append(project_data)
                    logger.debug(f"Added to projects: {json.dumps(project_data, indent=2)}")
                
                # Add to experience if it's a significant project
                if repo['stargazers_count'] > 0 or commit_count > 10:
                    exp_data = {
                        'company': repo['name'].replace('_', ' ').replace('-', ' '),
                        'position': 'Lead Developer',
                        'date': f"{repo['created_at'][:7]} - {repo['updated_at'][:7]}",
                        'description': description
                    }
                    experience.append(exp_data)
                    logger.debug(f"Added to experience: {json.dumps(exp_data, indent=2)}")
        
        # Extract education from bio
        education = []
        if user_data.get('bio'):
            education_data = {
                'school': 'Computer Science Student',  # You can update this based on actual data
                'degree': 'Bachelor of Science in Computer Science',
                'date': 'Present',
                'gpa': ''
            }
            education.append(education_data)
        
        # Add more comprehensive user data
        final_data = {
            'name': user_data.get('name', username),
            'email': user_data.get('email', ''),
            'phone': '',  # Add if available
            'location': user_data.get('location', ''),
            'bio': user_data.get('bio', ''),
            'skills': sorted(list(all_languages)),  # Sort skills alphabetically
            'projects': projects,
            'experience': experience,
            'education': education,
            'profile_url': github_url,
            'blog': user_data.get('blog', ''),
            'company': user_data.get('company', ''),
            'followers': user_data.get('followers', 0),
            'following': user_data.get('following', 0),
            'public_repos': user_data.get('public_repos', 0)
        }
        
        logger.debug(f"\nFinal processed data:\n{json.dumps(final_data, indent=2)}")
        return final_data
        
    except Exception as e:
        logger.error(f"GitHub API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def sanitize(text):
    if not text:
        return ""
    
    # Remove emojis and other special characters
    text = re.sub(r'[^\x00-\x7F]+', '', str(text))  # Remove non-ASCII characters
    
    # Replace LaTeX special characters
    replacements = {
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
        '~': '\\textasciitilde{}',
        '^': '\\textasciicircum{}',
        '\\': '\\textbackslash{}',
        '<': '\\textless{}',
        '>': '\\textgreater{}',
        '|': '$|$'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def generate_latex_resume(github_data):
    try:
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "resume_template.tex")
        with open(template_path, "r", encoding='utf-8') as f:
            template = f.read()

        # Format skills section
        programming_languages = [lang for lang in github_data['skills'] if lang in ['Python', 'JavaScript', 'TypeScript', 'C++', 'HTML', 'CSS', 'Jupyter Notebook']]
        technologies = [lang for lang in github_data['skills'] if lang not in programming_languages]
        
        skills_section = (
            "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
            "    \\small{\\item{\n"
            f"    \\textbf{{Programming Languages}}: {sanitize(', '.join(programming_languages))} \\\\\n"
            f"    \\textbf{{Technologies}}: {sanitize(', '.join(technologies))} \\\\\n"
            "    }}\n"
            "\\end{itemize}"
        )

        # Format experience section
        experience_items = []
        for exp in github_data['experience'][:3]:  # Take top 3 experiences
            description = sanitize(exp['description'])
            experience_items.append(
                "\\resumeSubheading\n"
                f"            {{{sanitize(exp['company'])}}}{{{sanitize(github_data['location'])}}}\n"
                f"            {{{sanitize(exp['position'])}}}{{{sanitize(exp['date'])}}}\n"
                "            \\resumeItemListStart\n"
                f"            \\resumeItem{{{description}}}\n"
                "            \\resumeItemListEnd"
            )
        experience_section = "\\resumeSubHeadingListStart\n" + "\n".join(experience_items) + "\n\\resumeSubHeadingListEnd"

        # Format projects section
        project_items = []
        for proj in github_data['projects'][:2]:  # Take top 2 projects to match template
            description = sanitize(proj['description'])
            languages = sanitize(', '.join(proj['languages']))
            project_items.append(
                "\\resumeSubheading\n"
                f"                {{{sanitize(proj['name'])}}}{{{sanitize('GitHub')}}}\n"
                f"                {{Project}}{{{languages}}}\n"
                "                \\resumeItemListStart\n"
                f"                \\resumeItem{{{description}}}\n"
                "                \\resumeItemListEnd"
            )
        projects_section = "\\resumeSubHeadingListStart\n" + "\n".join(project_items) + "\n\\resumeSubHeadingListEnd"

        # Format education section
        education_items = []
        for edu in github_data['education']:
            education_items.append(
                "\\resumeSubheading"
                f"{{{sanitize(edu['school'])}}}"
                f"{{{sanitize(github_data['location'])}}}"
                f"{{{sanitize(edu['degree'])}}}"
                f"{{{sanitize(edu['date'])}}}"
            )
        education_section = "\\resumeSubHeadingListStart\n" + "\n".join(education_items) + "\n\\resumeSubHeadingListEnd"

        # Create contact info section
        contact_section = (
            "\\begin{center}\n"
            f"\\small {sanitize(github_data['email'])} $|$ "
            f"\\href{{{sanitize(github_data['profile_url'])}}}{{{sanitize('GitHub')}}} $|$ "
            f"\\href{{{sanitize(github_data['blog'])}}}{{{sanitize('Portfolio')}}}\n"
            "\\end{center}"
        )

        # Replace sections in template
        replacements = {
            "\\textbf{\\Huge \\scshape John Doe}": f"\\textbf{{\\Huge \\scshape {sanitize(github_data['name'])}}}",
            "\\begin{itemize}[leftmargin=0.15in, label={}]\n    \\small{\\item{\n    \\textbf{Programming Languages}: JavaScript, TypeScript, HTML, Python, Jupyter Notebook, C++ \\\\\n    \\textbf{Technologies}: Git, GitHub \\\\\n    }}\n\\end{itemize}": skills_section,
            "\\resumeSubHeadingListStart\n\\resumeSubheading\n            {Example Corp}{Location}\n            {Software Engineer}{2020-Present}\n            \\resumeItemListStart\n            \\resumeItem{Full-stack development}\n            \\resumeItemListEnd\n\\resumeSubHeadingListEnd": experience_section,
            "\\resumeSubHeadingListStart\n\\resumeSubheading\n                {A-H-Website}{GitHub}\n                {Project}{HTML}\n                \\resumeItemListStart\n                \\resumeItem{So, I have created this website using HTML, CSS and JS and this is the first website in which I use JS and learn so much about JS different functions . In this website, I give every latest news on every major fields .It is like a latest news center in which I am updating information everyday so user get latest news}\n                \\resumeItemListEnd\n\\resumeSubheading\n                {Advent-Of-Code-2024-Competition}{GitHub}\n                {Project}{JavaScript}\n                \\resumeItemListStart\n                \\resumeItem{Welcome to my Advent of Code 2024 repository! 🎉 Every day, I'll be solving a new puzzle and posting my solution here. This event is a fun and challenging way to improve problem-solving skills and learn new concepts. I'm documenting my journey to share with anyone who might be working through the same puzzles or wants to follow along!🌟}\n                \\resumeItemListEnd\n\\resumeSubHeadingListEnd": projects_section,
            "\\resumeSubHeadingListStart\n\\resumeSubheading{University Name}{City, Country}{Degree}{2018-2022}\n\\resumeSubHeadingListEnd": education_section,
            "\\begin{center}\n\\small john@example.com $|$ \\href{https://github.com/HassanMehmood413}{GitHub} $|$ \\href{https://www.linkedin.com/in/hassan-mehmood-01a3a9247/}{LinkedIn}\n\\end{center}": contact_section
        }

        latex_content = template
        for key, value in replacements.items():
            latex_content = latex_content.replace(key, value)

        # Write the content to a file for debugging
        debug_path = os.path.join(os.path.dirname(__file__), "..", "temp", "debug_latex.tex")
        with open(debug_path, "w", encoding='utf-8') as f:
            f.write(latex_content)

        return latex_content
    except Exception as e:
        logger.error(f"LaTeX generation error: {str(e)}")
        logger.error(f"Error details: {str(e.__class__.__name__)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-resume")
async def generate_resume(profile_links: ProfileLinks, db=Depends(get_db)):
    try:
        logger.debug(f"\nReceived request with links:\nGitHub: {profile_links.github}\nLinkedIn: {profile_links.linkedin}")
        
        # Create temp directory
        temp_dir = os.path.join(os.path.dirname(__file__), "..", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        logger.debug(f"Created temp directory at: {temp_dir}")

        # Fetch GitHub data
        github_data = fetch_github_data(profile_links.github)

        # Generate LaTeX content
        latex_content = generate_latex_resume(github_data)
        logger.debug(f"\nGenerated LaTeX content:\n{latex_content[:500]}...")

        # Save LaTeX file with UTF-8 encoding
        tex_path = os.path.join(temp_dir, "resume.tex")
        with open(tex_path, "w", encoding='utf-8') as f:
            f.write(latex_content)
        logger.debug(f"Saved LaTeX file to: {tex_path}")

        # Generate PDF using pdflatex
        pdflatex_cmd = r"D:\software\miktex\miktex\bin\x64\pdflatex.exe"
        logger.debug(f"Running pdflatex command: {pdflatex_cmd}")
        
        # Change working directory to temp_dir for pdflatex
        current_dir = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # First run
            process = subprocess.run(
                [pdflatex_cmd, "-interaction=nonstopmode", "resume.tex"],
                capture_output=True,
                encoding='latin1',  # Change encoding to latin1
                check=False
            )
            
            # Log the complete output
            logger.debug(f"PDF generation stdout:\n{process.stdout}")
            if process.stderr:
                logger.error(f"PDF generation stderr:\n{process.stderr}")
            
            if process.returncode != 0:
                # Read the log file for more details
                try:
                    with open(os.path.join(temp_dir, "resume.log"), 'r', encoding='latin1') as f:
                        log_content = f.read()
                        logger.error(f"PDF generation log:\n{log_content}")
                except Exception as e:
                    logger.error(f"Could not read log file: {str(e)}")
                
                raise HTTPException(status_code=500, detail="PDF generation failed. Check logs for details.")
            
            # Second run for proper formatting
            process = subprocess.run(
                [pdflatex_cmd, "-interaction=nonstopmode", "resume.tex"],
                capture_output=True,
                encoding='latin1',  # Change encoding to latin1
                check=False
            )
            
            if process.returncode != 0:
                logger.error(f"Second PDF generation run failed with return code {process.returncode}")
                logger.error(f"Second run stderr:\n{process.stderr}")
                raise HTTPException(status_code=500, detail="PDF generation failed on second run")
            
        finally:
            os.chdir(current_dir)
        
        logger.debug("PDF generation successful")

        # Read generated PDF
        pdf_path = os.path.join(temp_dir, "resume.pdf")
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        logger.debug(f"Read PDF file from: {pdf_path}")

        # Clean up temporary files
        for ext in [".tex", ".pdf", ".aux", ".log"]:
            try:
                os.remove(os.path.join(temp_dir, f"resume{ext}"))
                logger.debug(f"Cleaned up temporary file: resume{ext}")
            except OSError as e:
                logger.warning(f"Failed to clean up file resume{ext}: {str(e)}")

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=resume.pdf"}
        )

    except Exception as e:
        logger.error(f"Resume generation error: {str(e)}")
        logger.error(f"Error details: {str(e.__class__.__name__)}")
        raise HTTPException(status_code=500, detail=str(e))