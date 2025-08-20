import asyncio
import aiohttp
from fpdf import FPDF
import requests

# Hardcoded questions about GitHub repos
HARDCODED_QUESTIONS = [
    "What does this repository do?",
    "Describe its main libraries.",
    "What is its project structure?",
    "How can a new developer get started with this repository?",
]


def _ask_openrouter(question, model="openai/gpt-3.5-turbo", api_key=None):
    """
    Private function to query OpenRouter API for a response to a question.

    Args:
        question (str): The question to ask the model.
        model (str): The model to use for completion. Default is "openai/gpt-3.5-turbo".
        api_key (str): Your OpenRouter API key. If None, tries to use environment variable.

    Returns:
        dict: The JSON response from OpenRouter API.
    """
    import os
    url = "https://openrouter.ai/api/v1/chat/completions"
    if api_key is None:
        api_key = os.getenv("OPENROUTER_API_KEY", "YOUR_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}]
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

# Simulate Copilot API response (replace with real API endpoint)
async def ask_copilot(session, repo, question):
    _ask_openrouter(question, model="openai/gpt-3.5-turbo", api_key=None)
    # Simulated response; replace with actual API POST.
    await asyncio.sleep(0.5)  # simulate network delay
    return f"Simulated answer for '{repo}': {question}"
    

async def process_repo(session, repo, extra_questions=None):
    questions = HARDCODED_QUESTIONS.copy()
    if extra_questions:
        questions.append(extra_questions)
    answers = []
    for q in questions:
        ans = await ask_copilot(session, repo, q)
        answers.append((q, ans))
    return repo, answers

async def main(repos, extra_questions=None, pdf_filename="copilot_answers.pdf"):
    async with aiohttp.ClientSession() as session:
        tasks = [process_repo(session, repo, extra_questions) for repo in repos]
        results = await asyncio.gather(*tasks)
        
        # Generate PDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        for repo, qa_list in results:
            pdf.set_font("Arial", 'B', size=14)
            pdf.cell(0, 10, f"Repository: {repo}", ln=True)
            pdf.set_font("Arial", size=12)
            for q, a in qa_list:
                pdf.multi_cell(0, 10, f"Q: {q}\nA: {a}\n")
            pdf.ln(5)
        
        pdf.output(pdf_filename)
        print(f"Answers saved to {pdf_filename}")

if __name__ == "__main__":
    # Example usage
    repos = [
        "netlify/PayPal-Go-SDK",
        "octocat/Hello-World",
        "psf/requests"
    ]
    extra_q = "What are the recent major changes in this repository?"
    asyncio.run(main(repos, extra_questions=extra_q))