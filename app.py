import gradio as gr
from tasks import LegalRAGSystem
import os
import markdown2

# Define EXAMPLE_QUERIES directly in app.py as the source of truth for the UI
APP_EXAMPLE_QUERIES = [
    "How do recent AAO decisions evaluate an applicant's Participation as a Judge service criteria?",
    "What characteristics of national or international awards persuade the AAO that they constitute 'sustained acclaim'?",
    "What does the AAO consider as qualifying 'original contributions of major significance' in EB-1A cases?",
    "How does the AAO evaluate membership in associations that require outstanding achievements?",
  ]

# Initialize the RAG system globally
rag_system = LegalRAGSystem()

def format_search_result(result):
    """Format a single search result with metadata"""
    # Format metadata
    metadata = f"""<div class='metadata'>
        📄 Source: {result["source_file"]} (Page {result["page_number"]})
        | 📅 Date: {result.get("decision_date", "N/A")}
        | 📋 Type: {result.get("petition_type", "N/A")}
        | ⚖️ Outcome: {result.get("decision_outcome", "N/A")}
        <span class='relevance-score'>Relevance: {result["score"]:.2f}</span>
    </div>"""
    
    # Combine all parts
    return f"<div class='search-result'>{result['text']}{metadata}</div>"

def format_final_answer(answer, results=None):
    """Format the final answer with search results if available"""
    if not answer:
        return "<div class='error'>No answer was generated.</div>"
    
    try:
        # Convert markdown to HTML
        html_answer = markdown2.markdown(answer)
        
        # Format the main answer
        formatted_answer = f"<div class='main-answer'>{html_answer}</div>"
        
        # Add formatted search results if available
        if results and isinstance(results, list) and not any(isinstance(r, dict) and 'info' in r for r in results):
            formatted_answer += "<div class='search-results'><h3>Supporting Evidence</h3>"
            for result in results:
                if isinstance(result, dict):
                    formatted_answer += format_search_result(result)
            formatted_answer += "</div>"
        
        return f"""
        <div class='rag-response'>
            {formatted_answer}
        </div>
        """
    except Exception as e:
        print(f"Error formatting answer: {str(e)}")
        # Fallback to plain text if markdown conversion fails
        return f"<div class='rag-response'><div class='main-answer'><pre>{answer}</pre></div></div>"

def legal_rag_interface(query_str):
    """Gradio interface function for the RAG system."""
    if not query_str.strip():
        return "⚠️ Please enter a query."

    try:
        print(f"🚀 Processing query: {query_str}")
        
        # Direct synchronous call
        result = rag_system.answer_query(query_str)
        print(f"✅ Got result type: {type(result)}")
        
        if isinstance(result, tuple) and len(result) == 2:
            answer, search_results = result
            print(f"📝 Answer length: {len(answer)} characters")
            
            # Convert markdown to HTML
            try:
                html_answer = markdown2.markdown(answer)
                return f"""
                <div style='padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-family: Arial, sans-serif; line-height: 1.6;'>
                    {html_answer}
                </div>
                """
            except Exception as e:
                print(f"⚠️ Markdown conversion failed: {e}")
                # Fallback to plain text with basic formatting
                return f"""
                <div style='padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-family: Arial, sans-serif; line-height: 1.6; white-space: pre-wrap;'>
                    {answer}
                </div>
                """
        else:
            print(f"⚠️ Unexpected result format: {type(result)}")
            return f"""
            <div style='padding: 20px; background: white; border-radius: 8px; color: #666;'>
                {str(result)}
            </div>
            """
            
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"❌ {error_msg}")
        return f"""
        <div style='padding: 20px; background: #fff3cd; border: 1px solid #ffeeba; border-radius: 8px; color: #856404;'>
            ⚠️ {error_msg}
        </div>
        """

# Custom CSS for a professional law-themed interface
custom_css = """
body {
    font-family: 'Times New Roman', Times, serif;
    background-color: #f4f6f8; /* Light grey background for a clean, modern feel */
    color: #333;
    line-height: 1.6;
}

.gradio-container {
    max-width: 1200px;
    margin: 20px auto;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
    overflow: hidden; /* Ensures child elements adhere to border radius */
}

/* Main title styling */
.title h1 {
    font-family: 'Times New Roman', Times, serif; /* Classic serif font for main title */
    font-size: 2.8em;
    font-weight: 700;
    color: #0A2342; /* Deep Navy Blue - for authority and trust */
    text-align: center;
    padding: 30px 20px 10px 20px;
    background-color: #ffffff; /* White background for the header area */
    border-bottom: 1px solid #dee2e6;
    margin: 0;
}

.description {
    font-family: 'Times New Roman', Times, serif;
    text-align: center;
    margin: 10px 20px 30px 20px;
    color: #555;
    font-size: 1.1em;
    background-color: #ffffff;
    padding-bottom: 30px;
}

/* Content area styling */
.main-content-area {
    padding: 25px;
    background-color: #ffffff; /* White background for content */
}

/* Input field styling */
.input-field textarea, .input-field input {
    border-radius: 8px !important;
    border: 1px solid #ced4da !important;
    padding: 12px 15px !important;
    font-size: 1em !important;
    background-color: #f8f9fa !important;
    color: #333 !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

.input-field textarea:focus, .input-field input:focus {
    border-color: #0A2342 !important; /* Navy blue focus */
    box-shadow: 0 0 0 3px rgba(10, 35, 66, 0.15) !important;
}

/* Button styling */
button.primary {
    background: #0A2342 !important; /* Deep Navy Blue */
    border: none !important;
    color: white !important;
    padding: 12px 20px !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    transition: background-color 0.2s ease, transform 0.1s ease !important;
    font-size: 1.05em !important;
    display: block;
    width: 100%;
    margin-top: 10px;
}

button.primary:hover {
    background: #001f3f !important; /* Darker Navy Blue on hover */
    transform: translateY(-1px) !important;
}

/* Output area styling */
.output-box .gradio-html {
    background-color: #ffffff !important;
    border: 1px solid #dee2e6 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
    padding: 25px !important; /* Increased padding */
    min-height: 400px; /* Ensure a decent height */
    display: flex; /* Use flexbox for alignment */
    flex-direction: column; /* Stack children vertically */
    /* justify-content: center; /* Center content vertically if needed, but might not be ideal for long responses */
}

.output-box-placeholder {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%; /* Take full height of parent */
    min-height: 350px; /* Match approx content area */
    color: #6c757d; /* Muted text color */
    font-size: 1.1em;
    text-align: center;
}

.output-box .rag-response {
    font-size: 0.95em;
    width: 100%; /* Ensure it takes full width */
}

/* Style for Gradio's native processing/status indicator if possible */
.gradio-container .generating {
    background-color: rgba(255, 255, 255, 0.8) !important; /* Lighten it up */
    color: #0A2342 !important; /* Match theme */
    padding: 10px 15px !important;
    border-radius: 6px !important;
    font-size: 0.9em !important;
}

.gradio-container .generating span:first-child { /* Target the spinner/icon if any */
    margin-right: 8px !important;
}

.output-box .main-answer h1, .output-box .main-answer h2 {
    font-family: 'Times New Roman', Times, serif;
    color: #0A2342;
    border-bottom: 1px solid #e9ecef;
    padding-bottom: 5px;
    margin-top: 15px;
    margin-bottom: 10px;
}

.output-box .main-answer h1 {
    font-size: 1.6em;
}

.output-box .main-answer h2 {
    font-size: 1.4em;
}

.output-box .main-answer p {
    margin-bottom: 12px;
    color: #333;
}

.output-box .main-answer strong, .output-box .main-answer b {
    color: #001f3f;
}

.output-box .main-answer ul, .output-box .main-answer ol {
    padding-left: 25px;
    margin-bottom: 12px;
}

.output-box .main-answer code {
    background-color: #e9ecef;
    padding: 2px 5px;
    border-radius: 4px;
    font-family: 'Courier New', Courier, monospace;
    color: #0A2342;
}

.output-box .main-answer pre {
    background-color: #e9ecef;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
}

.output-box .main-answer blockquote {
    border-left: 3px solid #c5b358; /* Gold-ish accent for blockquotes */
    padding-left: 15px;
    margin-left: 0;
    color: #555;
    font-style: italic;
}

.output-box .sources-section {
    margin-top: 20px;
    padding-top: 15px;
    border-top: 1px dashed #ced4da;
}

.output-box .sources-section h3 {
    font-family: 'Times New Roman', Times, serif;
    color: #0A2342;
    font-size: 1.2em;
    margin-bottom: 8px;
}

.output-box .sources-section p {
    font-size: 0.9em;
    color: #555;
}

/* Example queries styling */
.examples-title {
    font-family: 'Times New Roman', Times, serif;
    text-align: center;
    margin-top: 25px;
    margin-bottom: 10px;
    color: #0A2342;
    font-weight: 600;
    font-size: 1.5em;
}

.gradio-examples .examples {
    display: grid !important;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important;
    gap: 12px !important;
    padding: 0 20px 20px 20px;
    background-color: #ffffff;
}

.gradio-examples .example {
    background-color: #f8f9fa !important;
    border: 1px solid #dee2e6 !important;
    border-radius: 8px !important;
    padding: 12px !important;
    font-size: 0.95em !important;
    color: #333 !important;
    transition: box-shadow 0.2s ease, transform 0.2s ease !important;
}

.gradio-examples .example:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    transform: translateY(-2px) !important;
    border-color: #c5b358 !important; /* Gold-ish border on hover */
}

/* Custom class for error messages in output */
.error-message {
    background-color: #f8d7da; /* Light red for errors */
    color: #721c24; /* Dark red text */
    border: 1px solid #f5c6cb;
    padding: 15px;
    border-radius: 8px;
    margin-top: 10px;
}

/* Footer */
.footer {
    text-align: center;
    padding: 20px;
    font-size: 0.9em;
    color: #6c757d;
    background-color: #e9ecef;
    border-top: 1px solid #dee2e6;
    margin-top: 0; /* Ensure it connects if .gradio-container has bottom padding */
}
"""

# Modify the Gradio Interface for better layout and apply CSS
with gr.Blocks(css=custom_css, theme=gr.themes.Soft(primary_hue="blue", secondary_hue="orange")) as demo:
    with gr.Column(elem_classes=["container"]):
        gr.HTML("<div class='title'><h1>LegalRagBot ⚖️</h1></div><div class='description'>Your AI Legal Research Assistant for AAO Decisions. Ask a question about EB-1A criteria.</div>")

        with gr.Row(elem_classes=["main-content-area"]):
            with gr.Column(scale=1):
                query_input = gr.Textbox(
                    label="Enter Your Legal Query:",
                    placeholder="e.g., How is 'sustained acclaim' evaluated by the AAO?",
                    lines=3,
                    elem_classes=["input-field"]
                )
                submit_button = gr.Button("Analyze", variant="primary")
                
                gr.HTML("<h2 class='examples-title'>Example Queries</h2>")
                gr.Examples(
                    examples=APP_EXAMPLE_QUERIES,
                    inputs=query_input,
                    label=""
                )

            with gr.Column(scale=2):
                # Define output_display with a default empty state
                output_display = gr.HTML(
                    label="Analysis & Supporting Evidence",
                    value="<div class='output-box-placeholder'>Your analysis will appear here.</div>",
                    elem_classes=["output-box"]
                )
        
        gr.HTML("<div class='footer'>LegalRagBot © 2025 - AI-Powered Legal Insights</div>")

    # Update the process_query function to use the new formatter and handle errors
    def process_query_updated(query_str):
        if not query_str.strip():
            return "<div class='error-message'>⚠️ Please enter a query.</div>"
        try:
            print(f"🚀 Processing query: {query_str}")
            answer = rag_system.answer_query(query_str)
            
            # The answer_query now directly returns the final string from the formatting agent
            if isinstance(answer, str):
                # Check if it's an error message from the RAG system itself
                if answer.startswith("⚠️ Error") or answer.startswith("System error:"):
                     return f"<div class='error-message'>{answer}</div>"
                
                # If successful, format the answer using markdown2 for HTML conversion
                # Ensure the 'Sources:' section is styled if present
                html_answer = markdown2.markdown(answer, extras=["tables", "fenced-code-blocks"])
                
                # Simple way to style the 'Sources:' section if it exists
                if "\nSources:" in answer or "\n**Sources:**" in answer:
                    parts = html_answer.split("<h3>Sources:</h3>", 1)
                    if len(parts) == 2:
                        html_answer = parts[0] + "<div class='sources-section'><h3>Sources:</h3>" + parts[1] + "</div>"
                    else: # Try with bolded version
                        parts = html_answer.split("<h3><strong>Sources:</strong></h3>", 1)
                        if len(parts) == 2:
                           html_answer = parts[0] + "<div class='sources-section'><h3><strong>Sources:</strong></h3>" + parts[1] + "</div>"
                
                return f"<div class='rag-response'>{html_answer}</div>"
            else:
                return f"<div class='error-message'>⚠️ Unexpected result format: {type(answer)}. Expected a string.</div>"
            
        except Exception as e:
            error_msg = f"An unexpected error occurred in the interface: {str(e)}"
            print(f"❌ Interface Error: {error_msg}")
            return f"<div class='error-message'>⚠️ {error_msg}</div>"

    submit_button.click(
        fn=process_query_updated,
        inputs=query_input,
        outputs=output_display,
        api_name="analyze_legal_query"
    )

if __name__ == "__main__":
    if os.getenv("GRADIO_SERVER_NAME"): # Check if running in a specific server environment
        demo.launch(server_name=os.getenv("GRADIO_SERVER_NAME"), 
                    server_port=int(os.getenv("GRADIO_SERVER_PORT", 7860)),
                    share=os.getenv("GRADIO_SHARE", "False").lower() == "true")
    else:
        demo.launch(share=True) # Default to sharing for easy access if not specified 