from crewai import Agent, LLM
from tools import SeleniumTool, PineconeSearchTool
import os
from dotenv import load_dotenv

# Load environment variables

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Using Gemini 1.5 Flash for agentic tool use
gemini_llm = LLM(
    model="gemini/gemini-1.5-flash",
    api_key=GEMINI_API_KEY,
    temperature=0.3
)

# Using Gemini 2.0 Flash for advanced agentic tool use
advanced_gemini_llm = LLM(
    model="gemini/gemini-2.0-flash",
    api_key=GEMINI_API_KEY,
    temperature=0.3
)

# PDF Link Extractor Agent
scraper = Agent(
    role="PDF Link Extractor",
    goal=(
        "Use SeleniumTool to find ALL PDF links and their titles on the USCIS AAO Non-Precedent Decisions page. "
        "Return the findings as a list of dictionaries."
    ),
    backstory=(
        "You are a web scraping specialist focused on link extraction. "
        "Your task is to accurately find all PDF links and their corresponding titles from the specified USCIS URL: "
        "'https://www.uscis.gov/administrative-appeals/aao-decisions/aao-non-precedent-decisions?uri_1=19&m=2&y=1&items_per_page=25'. "
        "You only need to use SeleniumTool for this. Your final output should be a clean list of dictionaries, each containing 'url' and 'title'."
    ),
    tools=[SeleniumTool()],
    verbose=True,
    llm=gemini_llm,
    allow_delegation=False,
    memory=False,
    max_iter=10
)

# Initialize tools
search_tool = PineconeSearchTool()

# Legal Document Retrieval and Analysis Specialist
legal_retriever = Agent(
    role="Legal Document Retrieval and Analysis Specialist",
    goal=(
        "First, assess if the user's query is related to USCIS AAO decisions, U.S. immigration law, or closely related legal topics. "
        "If the query is relevant, search for pertinent legal document chunks using PineconeSearchTool (top_k=3, score_threshold=0.4) and return the raw search results. "
        "If the query is deemed off-topic or irrelevant to these legal areas, you MUST return the exact string 'OUT_OF_CONTEXT_QUERY' and perform NO search."
    ),
    backstory=(
        "You are a legal research expert specializing in U.S. immigration law and AAO decisions. "
        "Your primary responsibility is to determine if a query falls within your domain of expertise. "
        "If it does, you find precise document chunks using semantic search. "
        "If the query is outside the scope of USCIS AAO decisions or U.S. immigration law, you must clearly indicate this by returning 'OUT_OF_CONTEXT_QUERY' instead of searching."
    ),
    tools=[search_tool],
    verbose=True,
    max_iter=3,
    memory=False,
    llm=advanced_gemini_llm,
    allow_delegation=False
)

# Legal Response Formatter Agent
legal_formatter = Agent(
    role="Legal Response Formatter",
    goal=(
        "Create detailed legal analysis (analytical content: 1000-1750 chars). "
        "Append a '**Sources:**' section (excluded from char count) with citations formatted as: "
        "'Immigrant Petition for Alien Worker Extraordinary Ability (p. PAGENUMBER) - Month DD, YYYY'."
    ),
    backstory=(
        "You are a legal writing specialist. Your primary task is to generate substantive analysis of AAO decisions, ensuring the core text is between 1000-1750 characters. "
        "You write in a clear, flowing style with NO in-text citations, NO parenthetical references, and NO page numbers within the analysis content. Your analytical text should read naturally without any interruptions. "
        "After completing the analysis, you meticulously add a '**Sources:**' heading, followed by a single paragraph listing all sources. "
        "Each source within this paragraph is formatted as: 'Immigrant Petition for Alien Worker Extraordinary Ability (p. PAGENUMBER) - Month DD, YYYY', and individual sources are separated by a comma and a space. "
        "You MUST use the EXACT metadata values from search results: use the actual `page_number` (e.g., 4.0 becomes 'p. 4') and convert the actual `decision_date` from 'MMMDDYYYY' format (e.g., 'FEB032025' becomes 'Feb 03, 2025'). "
        "You NEVER fabricate, guess, or invent page numbers or dates - you only use what appears in the search result metadata. "
        "You understand that the Sources section (heading and paragraph) is NOT part of the character count for the main analysis. You avoid formal legal references (CFR, USC, etc.) in favor of natural, readable prose."
    ),
    tools=[],
    verbose=True,
    max_iter=2,
    memory=False,
    llm=advanced_gemini_llm,
    allow_delegation=False
)

