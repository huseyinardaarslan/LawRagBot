# main.py
import sys
from tasks import LegalRAGSystem

# Define the specific example queries
EXAMPLE_QUERIES = [
    "How do recent AAO decisions evaluate an applicant's Participation as a Judge service criteria?",
    "What characteristics of national or international awards persuade the AAO that they constitute 'sustained acclaim'?",
    "What does the AAO consider as qualifying 'original contributions of major significance' in EB-1A cases?",
    "How does the AAO evaluate membership in associations that require outstanding achievements?",
    "What evidence convinces the AAO that an applicant played a leading or critical role for distinguished organizations?"
]

def run_terminal_rag():
    """Runs the RAG system with input from the terminal."""
    rag_system = LegalRAGSystem()

    print("⚖️ Legal RAG System - Terminal Test")
    print("="*40)

    while True:
        print("\nChoose an option:")
        print("1. Run an example query")
        print("2. Enter a custom query")
        print("3. Exit")
        
        choice = input("Enter your choice (1-3): ").strip()

        query_to_run = None

        if choice == '1':
            print("\nAvailable example queries:")
            for i, ex_query in enumerate(EXAMPLE_QUERIES, 1):
                print(f"{i}. {ex_query}")
            
            try:
                example_choice = int(input(f"Enter example number (1-{len(EXAMPLE_QUERIES)}): ").strip())
                if 1 <= example_choice <= len(EXAMPLE_QUERIES):
                    query_to_run = EXAMPLE_QUERIES[example_choice - 1]
                else:
                    print("Invalid example number.")
                    continue
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue
        
        elif choice == '2':
            query_to_run = input("\nEnter your custom query: ").strip()
            if not query_to_run:
                print("Query cannot be empty.")
                continue
        
        elif choice == '3':
            print("Exiting. Goodbye!")
            break
        
        else:
            print("Invalid choice. Please enter a number between 1 and 3.")
            continue

        if query_to_run:
            print(f"\n🚀 Processing query: '{query_to_run}'")
            try:
                # Using coordinator for a more complete answer, similar to Gradio app
                result = rag_system.answer_query(query_to_run)
                print("\n📋 RAG System Answer:")
                print("-"*40)
                print(result)
                print("-"*40)
            except Exception as e:
                print(f"\n❌ Error during RAG processing: {str(e)}")

if __name__ == "__main__":
    # Check for command-line arguments for non-interactive mode
    if len(sys.argv) > 1:
        query_arg = " ".join(sys.argv[1:])
        if query_arg:
            print(f"⚖️ Legal RAG System - Command Line Query")
            print(f"🚀 Processing query: '{query_arg}'")
            rag_system_cl = LegalRAGSystem()
            try:
                result_cl = rag_system_cl.answer_query(query_arg)
                print("\n📋 RAG System Answer:")
                print("-"*40)
                print(result_cl)
                print("-"*40)
            except Exception as e_cl:
                print(f"\n❌ Error during RAG processing: {str(e_cl)}")
        else:
            run_terminal_rag() # Fallback to interactive if args are empty
    else:
        run_terminal_rag() # Default to interactive mode 