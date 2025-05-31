from crewai import Task, Crew
from textwrap import dedent
from agents import legal_retriever, legal_formatter
import os
from dotenv import load_dotenv
from typing import Union, Tuple, List, Dict

load_dotenv()

# USCIS PDF Link Extraction Task
scrape_task = Task(
    description=dedent("""
        Your SOLE mission is to identify ALL PDF files and their titles from the USCIS AAO Non-Precedent Decisions page
        and return ONLY a Python list of dictionaries.
        Target URL: 'https://www.uscis.gov/administrative-appeals/aao-decisions/aao-non-precedent-decisions?uri_1=19&m=2&y=1&items_per_page=25'

        **CRITICAL EXECUTION PLAN:**
        1.  Use `SeleniumTool` to navigate to the Target URL.
        2.  Extract a complete list of all PDF URLs and their corresponding titles from the page.
        3.  Your final, direct output MUST be ONLY the Python list of dictionaries. No other text, no explanations, no summaries.

        Example of the exact output format required:
        `[{'url': 'https://example.com/doc1.pdf', 'title': 'Title 1'}, {'url': 'https://example.com/doc2.pdf', 'title': 'Title 2'}]`

        **DO NOT** include any other text, formatting, or narrative around this list.
        **DO NOT** attempt to download files. Only extract link information.
    """),
    expected_output=dedent("""
        A Python list of dictionaries. Each dictionary MUST contain 'url' and 'title' keys for a PDF.
        The entire output MUST be ONLY this list.
        
        Correct Format Example:
        `[
            {"url": "https://www.uscis.gov/sites/default/files/err/.../FILE_A.pdf", "title": "Title of PDF A"},
            {"url": "https://www.uscis.gov/sites/default/files/err/.../FILE_B.pdf", "title": "Title of PDF B"}
        ]`

        Incorrect Format (DO NOT USE):
        `"Thought: I found the links. Here is the list: [...list...]"`
        `"Final Answer: The list of PDFs is: [...list...]"`
        `"Phase 1: Links Found: [...list...]"`

        Return ONLY the list structure itself: `[{"url": "...", "title": "..."}, ...]`
        If no PDFs are found, return an empty list: `[]`.
        If an error occurs that prevents list creation, return: `[{"error": "Error details here..."}]`
    """),
    agent=None,  # Will be assigned in main script
    tools=[] # SeleniumTool is the primary tool
)

class LegalRAGSystem:
    """Legal RAG System for AAO Decision Analysis"""
    
    def __init__(self):
        self.legal_retriever = legal_retriever
        self.legal_formatter = legal_formatter
    
    def create_search_task(self, query: str) -> Task:
        """Create a search task that only focuses on finding relevant documents."""
        return Task(
            description=(
                f"Your first critical step is to evaluate if the user's query: '{query}' is directly related to USCIS AAO decisions, U.S. immigration law, or closely related legal topics.\n\n"
                f"RELEVANCE ASSESSMENT:\n"
                f"1. If the query is NOT related to these specific legal areas, your ONLY output MUST be the exact string: 'OUT_OF_CONTEXT_QUERY'. Do NOT proceed to search.\n"
                f"2. If the query IS relevant, then proceed with the search.\n\n"
                f"SEARCH INSTRUCTIONS (only if query is relevant):\n"
                f"1. Use PineconeSearchTool with top_k=3, score_threshold=0.4 for the query: '{query}'.\n"
                f"2. Return ONLY the raw search results from PineconeSearchTool.\n"
                f"3. Do not provide any analysis or conclusions.\n\n"
                f"Your output will either be the exact string 'OUT_OF_CONTEXT_QUERY' OR the list of search result dictionaries."
            ),
            expected_output="Either the exact string 'OUT_OF_CONTEXT_QUERY' if the query is off-topic, OR a list of search result dictionaries from PineconeSearchTool with all metadata if the query is relevant.",
            agent=self.legal_retriever
        )
    
    def create_formatting_task(self, query: str) -> Task:
        """Create a formatting task that analyzes search results and creates a proper response."""
        return Task(
            description=(
                f"You will receive search results from the previous task. Your job is to analyze them and create "
                f"a comprehensive answer to: '{query}'\n\n"
                f"ANALYSIS INSTRUCTIONS:\n"
                f"1. Review each search result thoroughly\n"
                f"2. Extract and synthesize key information\n"
                f"3. Focus on substantive legal principles and findings\n"
                f"4. Note patterns and important precedents\n\n"
                f"RESPONSE FORMAT:\n"
                f"1. Start with a clear title using # heading.\n"
                f"2. Provide substantive analysis in 2-3 key points. This analytical content MUST be between 1000-1750 characters.\n"
                f"3. Focus on explaining legal principles and AAO reasoning.\n"
                f"4. CRITICAL: Write FLOWING text with NO in-text citations, NO parenthetical references, NO page numbers within the analysis. Keep the content natural and readable.\n"
                f"5. After the analytical content, add a '**Sources:**' heading.\n"
                f"6. List all sources in a single paragraph immediately following the '**Sources:**' heading. Each source should be formatted as: Immigrant Petition for Alien Worker Extraordinary Ability (p. PAGENUMBER) - Month DD, YYYY.\n"
                f"   Separate individual sources within this paragraph with a comma and a space (e.g., Source 1, Source 2, Source 3).\n"
                f"   - You MUST use the EXACT `page_number` and `decision_date` values from the search result metadata. DO NOT fabricate or guess these values.\n"
                f"   - Convert the `decision_date` format from 'MMMDDYYYY' (e.g., 'FEB032025') to 'Month DD, YYYY' (e.g., 'Feb 03, 2025').\n"
                f"   - Use the exact `page_number` from metadata (e.g., if metadata shows 'page_number': 4.0, use 'p. 4').\n"
                f"   - Example with real metadata: **Sources:** Immigrant Petition for Alien Worker Extraordinary Ability (p. 4) - Feb 03, 2025, Immigrant Petition for Alien Worker Extraordinary Ability (p. 2) - Feb 13, 2025\n"
                f"7. The '**Sources:**' section and its content are EXCLUDED from the 1000-1750 character count of the analytical content.\n"
                f"8. Prioritize information content over excessive citations within the analysis.\n\n"
                f"LENGTH REQUIREMENT (for analytical content only, excluding sources section):\n"
                f"- STRICTLY between 1000-1750 characters total\n"
                f"- 85% content/analysis, 15% citations (this ratio applies to how much of the *overall effort* should be on analysis vs. just listing sources, not a strict char count for sources themselves against the 1000-1750 limit).\n"
                f"- Be concise but informative.\n\n"
                f"IMPORTANT:\n"
                f"- Focus on what the AAO actually considers/evaluates\n"
                f"- Explain the reasoning behind decisions\n"
                f"- Only cite PDF filename and page number\n"
                f"- NO formal legal references (CFR, USC, etc.)\n"
                f"- Avoid over-citing - prefer content over citations"
            ),
            expected_output=(
                "A substantive markdown response (STRICTLY 750-1500 characters) focused on analysis and legal principles "
                "with 15% citations. Must respect character limits while providing comprehensive content."
            ),
            agent=self.legal_formatter
        )

    def answer_query(self, query: str) -> str:
        """Process a query using sequential crew workflow"""
        try:
            # Create sequential tasks
            search_task = self.create_search_task(query)
            
            print(f"🚀 Starting RAG analysis for: {repr(query)}")
            print("="*80)
            
            # Create a crew for the search task first
            search_crew = Crew(
                tasks=[search_task],
                agents=[self.legal_retriever],
                process="sequential",
                verbose=True
            )
            
            try:
                print("🔍 Executing Search Task...")
                search_result = search_crew.kickoff()
                print(f"Raw search_result: {search_result}")

                # Check if the query was out of context
                # Extract the actual result from CrewOutput object
                actual_result = str(search_result).strip()
                if actual_result == "OUT_OF_CONTEXT_QUERY":
                    print("⚠️ Query deemed out of context by the retriever agent.")
                    return "Your query is outside my area of expertise, which focuses on USCIS AAO decisions and U.S. immigration law. I cannot assist with this topic."
                
                # If we get here, the search returned actual results
                # Now create a single crew with both tasks for proper sequential processing
                formatting_task = self.create_formatting_task(query)
                
                # Create a single crew with both tasks in sequence
                full_crew = Crew(
                    tasks=[search_task, formatting_task],
                    agents=[self.legal_retriever, self.legal_formatter],
                    process="sequential",
                    verbose=True,
                    function_configs=[
                        {
                            "name": "PineconeSearchTool",
                            "description": "Semantic search in legal documents",
                            "parameters": {
                                "query": {"type": "string"},
                                "top_k": {"type": "integer", "default": 3},
                                "score_threshold": {"type": "number", "default": 0.4}
                            }
                        }
                    ]
                )
                
                print("✍️ Executing Full Sequential Workflow...")
                final_result = full_crew.kickoff()
                print("✅ RAG system completed successfully")
                
                if isinstance(final_result, str):
                    return final_result
                else:
                    return str(final_result)
                    
            except Exception as crew_error:
                print(f"❌ Crew error: {str(crew_error)}")
                return f"⚠️ Error in RAG processing: {str(crew_error)}"
                
        except Exception as e:
            error_msg = f"System error: {str(e)}"
            print(f"❌ {error_msg}")
            return f"⚠️ {error_msg}"

