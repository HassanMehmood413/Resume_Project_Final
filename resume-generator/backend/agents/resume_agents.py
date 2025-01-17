from typing import Dict, List, Any
import requests
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class DataCollectorAgent:
    """Collects and structures data from GitHub and LinkedIn"""
    def __init__(self, github_token: str):
        self.github_token = github_token
        self.headers = {
            'Authorization': f'Bearer {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

    def collect_github_data(self, github_url: str) -> Dict:
        username = github_url.split('/')[-1]
        
        # Fetch user data
        user_response = requests.get(
            f'https://api.github.com/users/{username}',
            headers=self.headers
        )
        user_data = user_response.json()
        
        # Fetch repositories
        repos_response = requests.get(
            f'https://api.github.com/users/{username}/repos',
            headers=self.headers
        )
        repos = repos_response.json()
        
        return {
            'user_data': user_data,
            'repositories': repos
        }

class ContentEnhancementAgent:
    """Enhances content using Serper API for professional writing"""
    def __init__(self, serper_api_key: str):
        self.api_key = serper_api_key
        self.headers = {
            'X-API-KEY': serper_api_key,
            'Content-Type': 'application/json'
        }

    def enhance_text(self, text: str, context: str) -> str:
        prompt = f"""
        Transform this {context} into professional resume content:
        - Use strong action verbs
        - Quantify achievements
        - Highlight technical skills
        - Maintain concise, impactful language
        
        Original: {text}
        """
        
        try:
            response = requests.post(
                'https://google.serper.dev/search',
                headers=self.headers,
                json={'q': prompt}
            )
            if response.status_code == 200:
                return response.json()['organic'][0]['snippet']
            return text
        except Exception as e:
            logger.error(f"Content enhancement error: {str(e)}")
            return text

class ResumeStructureAgent:
    """Organizes enhanced content into LaTeX template sections"""
    def __init__(self, template_path: str):
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()

    def format_section(self, section_type: str, content: Dict) -> str:
        if section_type == "skills":
            return self._format_skills(content)
        elif section_type == "experience":
            return self._format_experience(content)
        elif section_type == "projects":
            return self._format_projects(content)
        elif section_type == "education":
            return self._format_education(content)
        return ""

    def _format_skills(self, skills: List[str]) -> str:
        programming_languages = [s for s in skills if s in ['Python', 'JavaScript', 'TypeScript', 'C++', 'HTML', 'CSS']]
        technologies = [s for s in skills if s not in programming_languages]
        
        return (
            "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
            "    \\small{\\item{\n"
            f"    \\textbf{{Programming Languages}}: {', '.join(programming_languages)} \\\\\n"
            f"    \\textbf{{Technologies}}: {', '.join(technologies)} \\\\\n"
            "    }}\n"
            "\\end{itemize}"
        )

    def _format_experience(self, experiences: List[Dict]) -> str:
        items = []
        for exp in experiences[:3]:
            items.append(
                "\\resumeSubheading\n"
                f"            {{{exp['company']}}}{{{exp['location']}}}\n"
                f"            {{{exp['position']}}}{{{exp['date']}}}\n"
                "            \\resumeItemListStart\n"
                f"            \\resumeItem{{{exp['description']}}}\n"
                "            \\resumeItemListEnd"
            )
        return "\\resumeSubHeadingListStart\n" + "\n".join(items) + "\n\\resumeSubHeadingListEnd"

    def _format_projects(self, projects: List[Dict]) -> str:
        items = []
        for proj in projects[:2]:
            items.append(
                "\\resumeSubheading\n"
                f"                {{{proj['name']}}}{{{proj['platform']}}}\n"
                f"                {{Project}}{{{', '.join(proj['technologies'])}}}\n"
                "                \\resumeItemListStart\n"
                f"                \\resumeItem{{{proj['description']}}}\n"
                "                \\resumeItemListEnd"
            )
        return "\\resumeSubHeadingListStart\n" + "\n".join(items) + "\n\\resumeSubHeadingListEnd"

class ResumeWorkflow:
    """Coordinates the agents and manages the resume generation workflow"""
    def __init__(self, github_token: str, serper_api_key: str, template_path: str):
        self.github_token = github_token
        self.serper_api_key = serper_api_key
        self.template_path = template_path

    def escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters and remove emojis."""
        if not text:
            return ""
            
        # First remove emojis and other non-ASCII characters
        text = ''.join(char for char in text if ord(char) < 128)
        
        # Define LaTeX special characters and their escaped versions
        latex_special_chars = {
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
            '>': '\\textgreater{}'
        }
        
        # First, escape backslashes
        text = text.replace('\\', '\\textbackslash{}')
        
        # Then escape other special characters
        for char, escaped_char in latex_special_chars.items():
            if char != '\\':  # Skip backslash as we've already handled it
                text = text.replace(char, escaped_char)
        
        # Remove any remaining problematic characters
        text = ''.join(c for c in text if c.isprintable())
            
        return text.strip()

    def format_date(self, date_str: str) -> str:
        """Format date string for LaTeX."""
        # Add your date formatting logic here if needed
        return self.escape_latex(date_str)

    def format_experience_item(self, title: str, date_range: str, description: str) -> str:
        """Format a single experience item."""
        return (
            f"\\resumeSubheading\n"
            f"  {{{self.escape_latex(title)}}}{{{self.format_date(date_range)}}}\n"
            f"  \\resumeItemListStart\n"
            f"    \\resumeItem{{{self.escape_latex(description)}}}\n"
            f"  \\resumeItemListEnd\n"
        )

    def format_project_item(self, title: str, description: str) -> str:
        """Format a single project item."""
        return (
            f"\\resumeProjectHeading\n"
            f"  {{{self.escape_latex(title)}}}\n"
            f"  \\resumeItemListStart\n"
            f"    \\resumeItem{{{self.escape_latex(description)}}}\n"
            f"  \\resumeItemListEnd\n"
        )

    def generate_resume(self, github_url: str) -> str:
        """Generate LaTeX resume content."""
        try:
            # Fetch GitHub data
            data_collector = DataCollectorAgent(self.github_token)
            github_data = data_collector.collect_github_data(github_url)

            # Prepare data for resume
            data = {
                "name": github_data['user_data'].get('name', 'John Doe'),
                "email": "john@example.com",  # Placeholder, replace with actual data if available
                "location": "New York, NY",  # Placeholder, replace with actual data if available
                "skills": ["Python", "JavaScript", "LaTeX"],  # Placeholder, replace with actual data if available
                "experiences": [
                    {
                        "title": "Lead Developer",
                        "date_range": "2024-01 - Present",
                        "description": "Led development of key features"
                    }
                ],
                "projects": [
                    {
                        "title": "Resume Generator",
                        "description": "Automated resume generation system"
                    }
                ]
            }

            # Read template
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template = f.read()

            # Format sections
            experiences = "\n".join(
                self.format_experience_item(
                    exp["title"],
                    exp["date_range"],
                    exp["description"]
                ) for exp in data["experiences"]
            )

            projects = "\n".join(
                self.format_project_item(
                    proj["title"],
                    proj["description"]
                ) for proj in data["projects"]
            )

            skills = ", ".join(self.escape_latex(skill) for skill in data["skills"])

            # Replace placeholders in template
            resume_content = template.replace(
                "<<NAME>>", self.escape_latex(data["name"])
            ).replace(
                "<<EMAIL>>", self.escape_latex(data["email"])
            ).replace(
                "<<LOCATION>>", self.escape_latex(data["location"])
            ).replace(
                "<<EXPERIENCES>>", experiences
            ).replace(
                "<<PROJECTS>>", projects
            ).replace(
                "<<SKILLS>>", skills
            )

            return resume_content

        except Exception as e:
            logger.error(f"Error generating resume: {str(e)}")
            raise