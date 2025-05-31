import os
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pdfplumber
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
import re
from tqdm import tqdm
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

class DocumentChunk(BaseModel):
    """Pydantic model for document chunks with metadata"""
    id: str
    text: str
    source_file: str
    page_number: float
    chunk_index: int
    start_char: int
    end_char: int
    decision_date: Optional[str] = None
    petition_type: Optional[str] = None
    decision_outcome: Optional[str] = None

class DocumentProcessor:
    """Document processor for extracting chunks from legal PDFs"""
    
    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 300):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def process_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Process a PDF file and extract chunks with metadata"""
        chunks = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                page_texts = []
                
                # Extract text from each page
                print(f"📄 Extracting text from {Path(pdf_path).name}...")
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    page_texts.append((page_num, page_text))
                    full_text += f"\n--- Page {page_num} ---\n" + page_text
                
                if not full_text.strip():
                    print(f"⚠️ No text extracted from {pdf_path}")
                    return []
                
                # Extract metadata from filename and content
                filename = Path(pdf_path).name
                decision_date = self._extract_decision_date(filename, full_text)
                petition_type = self._extract_petition_type(full_text)
                decision_outcome = self._extract_decision_outcome(full_text)
                
                print(f"📊 Metadata extracted:")
                print(f"   Decision Date: {decision_date}")
                print(f"   Petition Type: {petition_type}")
                print(f"   Decision Outcome: {decision_outcome}")
                
                # Split text into chunks
                print(f"✂️ Splitting into chunks...")
                text_chunks = self.text_splitter.split_text(full_text)
                
                # Create DocumentChunk objects
                for chunk_idx, chunk_text in enumerate(text_chunks):
                    # Find which page this chunk belongs to
                    page_num = self._find_page_for_chunk(chunk_text, page_texts)
                    
                    chunk = DocumentChunk(
                        id=str(uuid.uuid4()),
                        text=chunk_text.strip(),
                        source_file=filename,
                        page_number=page_num,
                        chunk_index=chunk_idx,
                        start_char=full_text.find(chunk_text),
                        end_char=full_text.find(chunk_text) + len(chunk_text),
                        decision_date=decision_date,
                        petition_type=petition_type,
                        decision_outcome=decision_outcome
                    )
                    chunks.append(chunk.model_dump())
                
                print(f"✅ Created {len(chunks)} chunks from {len(pdf.pages)} pages")
                    
        except Exception as e:
            print(f"❌ Error processing {pdf_path}: {str(e)}")
            return []
        
        return chunks
    
    def process_all_pdfs(self, pdf_directory: str = "data/pdfs") -> List[Dict[str, Any]]:
        """Process all PDFs in a directory"""
        pdf_dir = Path(pdf_directory)
        if not pdf_dir.exists():
            print(f"❌ Directory {pdf_directory} does not exist")
            return []
        
        pdf_files = list(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"❌ No PDF files found in {pdf_directory}")
            return []
        
        print(f"📁 Found {len(pdf_files)} PDF files to process")
        
        all_chunks = []
        stats = {"successful": 0, "failed": 0, "total_chunks": 0}
        
        for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
            print(f"\n{'='*60}")
            chunks = self.process_pdf(str(pdf_path))
            
            if chunks:
                all_chunks.extend(chunks)
                stats["successful"] += 1
                stats["total_chunks"] += len(chunks)
                print(f"✅ Success: {len(chunks)} chunks")
            else:
                stats["failed"] += 1
                print(f"❌ Failed to process")
        
        print(f"\n{'='*60}")
        print(f"📊 PROCESSING SUMMARY:")
        print(f"   ✅ Successful: {stats['successful']} files")
        print(f"   ❌ Failed: {stats['failed']} files")
        print(f"   📝 Total chunks: {stats['total_chunks']}")
        print(f"   📈 Average chunks per file: {stats['total_chunks']/max(stats['successful'], 1):.1f}")
        
        return all_chunks
    
    def _extract_decision_date(self, filename: str, text: str) -> Optional[str]:
        """Extract decision date from filename or text"""
        # Try filename first
        date_patterns = [
            r'(FEB\d{2}2025)',
            r'(\d{4}_\d{2}_\d{2})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_petition_type(self, text: str) -> Optional[str]:
        """Extract petition type from text"""
        if "Extraordinary Ability" in text:
            return "EB-1A Extraordinary Ability"
        elif "Outstanding Professor" in text:
            return "EB-1B Outstanding Professor"
        elif "Multinational Manager" in text:
            return "EB-1C Multinational Manager"
        return "I-140"
    
    def _extract_decision_outcome(self, text: str) -> Optional[str]:
        """Extract decision outcome from text, prioritizing text after 'ORDER:' near the end."""
        # Focus on the last 2000 characters for the "ORDER:" statement
        last_portion = text[-2000:]
        order_match = re.search(r"ORDER:(.*?)(?=\n\n|$)", last_portion, re.IGNORECASE | re.DOTALL)

        if order_match:
            order_text = order_match.group(1).strip()
            
            # Define outcome keywords to search within the ORDER text
            outcome_keywords = {
                "Approved/Sustained": ["appeal is sustained", "petition is approved", "motion is granted", "request is granted"],
                "Denied/Dismissed": ["appeal is dismissed", "petition is denied", "motion is denied", "request is denied"],
                "Remanded": ["remand", "remanded", "return to", "additional evidence"]
            }
            
            for outcome, keywords in outcome_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in order_text.lower():
                        return outcome
        
        # Fallback: broader search in the beginning and end of the document
        beginning_text = text[:2000]
        ending_text = text[-2000:]
        combined_search_text = beginning_text + " " + ending_text
        
        outcome_keywords = {
            "Approved/Sustained": ["appeal is sustained", "petition is approved", "motion is granted", "request is granted"],
            "Denied/Dismissed": ["appeal is dismissed", "petition is denied", "motion is denied", "request is denied"],
            "Remanded": ["remand", "remanded", "return to", "additional evidence"]
        }
        
        for outcome, keywords in outcome_keywords.items():
            for keyword in keywords:
                if keyword.lower() in combined_search_text.lower():
                    return outcome
                
        return None
    
    def _find_page_for_chunk(self, chunk: str, page_texts: List[Tuple[int, str]]) -> int:
        """Find which page a chunk primarily belongs to"""
        max_overlap = 0
        best_page = 1
        
        for page_num, page_text in page_texts:
            overlap = len(set(chunk.split()) & set(page_text.split()))
            if overlap > max_overlap:
                max_overlap = overlap
                best_page = page_num
        
        return best_page

class EmbeddingGenerator:
    """Generate embeddings using sentence transformers"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        print(f"🤖 Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = 384
        print(f"📏 Embedding dimension: {self.embedding_dim}")

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        print(f"🔢 Generating embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts, show_progress_bar=True, batch_size=32)
        return embeddings.tolist()

class PineconeVectorStore:
    """Vector store using Pinecone for semantic search"""
    
    def __init__(self, api_key: str = None, index_name: str = "legal-documents"):
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.index_name = index_name
        self.embedding_generator = EmbeddingGenerator()
        
        if not self.api_key:
            raise ValueError("Pinecone API key is required")
        
        print("🌲 Connecting to Pinecone...")
        self.pc = Pinecone(api_key=self.api_key)
        print(f"📂 Index: {self.index_name}")

    def create_index(self):
        """Create a new Pinecone index with cosine similarity"""
        try:
            # Delete existing index if it exists
            if self.index_name in [index.name for index in self.pc.list_indexes()]:
                print(f"🗑️ Deleting existing index: {self.index_name}")
                self.pc.delete_index(self.index_name)
                print("⏳ Waiting for index deletion...")
                import time
                time.sleep(10)  # Wait for deletion to complete

            print(f"🆕 Creating new index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.embedding_generator.embedding_dim,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            print("✅ Index created successfully")
            
        except Exception as e:
            print(f"❌ Error creating index: {str(e)}")
            raise
    
    def store_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Store document chunks with dense vectors in Pinecone."""
        try:
            if not chunks:
                return {"status": "error", "message": "No chunks to store"}
            
            print(f"🔢 Processing {len(chunks)} chunks for dense vector storage...")
            
            self.create_index() # Ensure index is (re)created with cosine metric
            
            index = self.pc.Index(self.index_name)
            batch_size = 50
            stored_count = 0
            
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                texts = [chunk["text"] for chunk in batch]
                
                print(f"🔢 Generating dense embeddings for batch of {len(batch)} chunks...")
                embeddings = self.embedding_generator.generate_embeddings(texts)
            
                vectors_to_upsert = []
                for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                    metadata = {
                        "text": chunk["text"],
                        "source_file": chunk["source_file"],
                        "page_number": chunk["page_number"]
                    }
                    
                    if chunk.get("chunk_index") is not None:
                        metadata["chunk_index"] = chunk["chunk_index"]
                    if chunk.get("start_char") is not None:
                        metadata["start_char"] = chunk["start_char"]
                    if chunk.get("end_char") is not None:
                        metadata["end_char"] = chunk["end_char"]
                    if chunk.get("decision_date"):
                        metadata["decision_date"] = str(chunk["decision_date"])
                    if chunk.get("petition_type"):
                        metadata["petition_type"] = str(chunk["petition_type"])
                    if chunk.get("decision_outcome"):
                        metadata["decision_outcome"] = str(chunk["decision_outcome"])
                    
                    vector_data = {
                        "id": chunk.get("id", str(uuid.uuid4())),
                        "values": embedding,
                        "metadata": metadata
                    }
                    vectors_to_upsert.append(vector_data)
                
                index.upsert(vectors=vectors_to_upsert)
                stored_count += len(batch)
                print(f"✅ Stored {stored_count}/{len(chunks)} chunks (dense vectors only)")
            
            return {
                "status": "success",
                "chunks_stored": stored_count,
                "index": self.index_name,
                "embedding_dimension": self.embedding_generator.embedding_dim
            }
            
        except Exception as e:
            print(f"❌ Error storing chunks: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def search_similar(self, query: str, top_k: int = 10, score_threshold: float = 0.6) -> List[Dict[str, Any]]:
        """Semantic search using dense vectors only."""
        try:
            print(f"🔍 Performing semantic search for: '{query}' (dense vectors only)")
            
            index = self.pc.Index(self.index_name)
            query_embedding = self.embedding_generator.generate_embeddings([query])[0]
            
            # Perform dense vector search only
            search_results = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            results = []
            for result in search_results['matches']:
                if result['score'] >= score_threshold:
                    results.append({
                        "id": result['id'],
                        "score": result['score'],
                        "text": result['metadata']["text"],
                        "source_file": result['metadata']["source_file"],
                        "page_number": result['metadata']["page_number"],
                        "decision_date": result['metadata'].get("decision_date"),
                        "petition_type": result['metadata'].get("petition_type"),
                        "decision_outcome": result['metadata'].get("decision_outcome")
                    })
            
            print(f"📊 Found {len(results)} relevant chunks through semantic search")
            return results
            
        except Exception as e:
            print(f"❌ Error during semantic search: {str(e)}")
            return []

def setup_complete_system(pdf_directory: str = "data/pdfs", pinecone_api_key: str = None) -> Dict[str, Any]:
    """Complete setup: process documents and store in Pinecone"""
    
    print("🚀 STARTING COMPLETE RAG SYSTEM SETUP")
    print("="*80)
    
    # Step 1: Process all documents
    print("\n📝 STEP 1: Processing PDF Documents")
    print("-"*40)
    processor = DocumentProcessor()
    chunks = processor.process_all_pdfs(pdf_directory)
    
    if not chunks:
        return {
            "status": "error",
            "message": "No documents were successfully processed"
        }
    
    # Step 2: Store in Pinecone
    print(f"\n🗄️ STEP 2: Storing in Pinecone Vector Database")
    print("-"*40)
    vector_store = PineconeVectorStore(api_key=pinecone_api_key)
    result = vector_store.store_chunks(chunks)
    
    if result["status"] == "error":
        return result
    
    print(f"\n🎉 SETUP COMPLETED SUCCESSFULLY!")
    print("="*80)
    print(f"📊 Total chunks processed: {len(chunks)}")
    print(f"🗄️ Chunks stored in Pinecone: {result['chunks_stored']}")
    print(f"📏 Embedding dimension: {result['embedding_dimension']}")
    print(f"📂 Index name: {result['index']}")
    
    return {
        "status": "success",
        "message": "RAG system setup completed successfully",
        "total_chunks": len(chunks),
        "stored_chunks": result["chunks_stored"],
        "index": result["index"]
    }

def test_system(query: str = "How do AAO decisions evaluate extraordinary ability criteria?", pinecone_api_key: str = None):
    """Test the system with a sample query"""
    print(f"\n🧪 TESTING SYSTEM")
    print("="*50)
    
    vector_store = PineconeVectorStore(api_key=pinecone_api_key)
    results = vector_store.search_similar(query, top_k=5)
    
    if results:
        print(f"✅ Test successful! Found {len(results)} relevant chunks")
        print(f"\nTop result:")
        print(f"  📄 Source: {results[0]['source_file']}")
        print(f"  📊 Score: {results[0]['score']:.3f}")
        print(f"  ⚖️ Decision Outcome: {results[0].get('decision_outcome', 'N/A')}")
        print(f"  📝 Text: {results[0]['text'][:200]}...")
    else:
        print("❌ Test failed - no results found")

if __name__ == "__main__":
    # Load Pinecone API key from environment variables
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    
    if not PINECONE_API_KEY:
        print("❌ Error: PINECONE_API_KEY must be set in .env file")
        print("📝 Example .env file:")
        print("PINECONE_API_KEY=your_api_key_here")
        exit(1)
    
    print(f"🔑 Using Pinecone API Key: {PINECONE_API_KEY[:20]}...")
    
    # Setup the complete system with Pinecone
    result = setup_complete_system(
        pdf_directory="data/pdfs",
        pinecone_api_key=PINECONE_API_KEY
    )
    
    if result["status"] == "success":
        print(f"\n🎉 SETUP COMPLETED SUCCESSFULLY!")
        print(f"📊 You can now check your Pinecone dashboard to see the stored documents")
        print(f"🔍 Total chunks stored: {result['stored_chunks']}")
    else:
        print(f"❌ Setup failed: {result['message']}") 