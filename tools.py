import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from robotexclusionrulesparser import RobotExclusionRulesParser
import logging
from crewai.tools import BaseTool
from pydantic import Field, BaseModel as PydanticBaseModel
from typing import Optional, List, Dict
import os
from urllib.parse import urlparse

class RobotsTxtCheckerTool(BaseTool):
    name: str = "RobotsTxtCheckerTool"
    description: str = "Checks if a URL is allowed to be crawled according to robots.txt"

    def _run(self, url: str) -> bool:
        return self.check(url)

    def check(self, url: str) -> bool:
        base_url = "/".join(url.split("/")[:3])
        robots_url = f"{base_url}/robots.txt"
        parser = RobotExclusionRulesParser()
        try:
            response = requests.get(robots_url, headers={"User-Agent": "LegalResearchBot/1.0"}, timeout=5)
            response.raise_for_status()
            parser.parse(response.text)
            allowed = parser.is_allowed("LegalResearchBot/1.0", url)
            logging.info(f"robots.txt check for {url}: {'Allowed' if allowed else 'Disallowed'}")
            return allowed
        except requests.exceptions.RequestException as e:
            logging.warning(f"Error accessing robots.txt ({robots_url}): {e}. Assuming allowed.")
            return True
        except Exception as e:
            logging.warning(f"Error parsing robots.txt for {url}: {e}. Assuming allowed.")
            return True

class RequestsTool(BaseTool):
    name: str = "RequestsTool"
    description: str = "Downloads PDF files from URLs to a specified directory"

    def _run(self, url: str, filename: str = None, directory: str = "data/pdfs") -> Dict[str, str]:
        return self.download_pdf(url, filename, directory)

    def download_pdf(self, url: str, filename: str = None, directory: str = "data/pdfs") -> Dict[str, str]:
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            # Generate filename if not provided
            if not filename:
                parsed_url = urlparse(url)
                filename = os.path.basename(parsed_url.path)
                if not filename or not filename.endswith('.pdf'):
                    filename = f"document_{int(time.time())}.pdf"
            
            # Ensure filename ends with .pdf
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            
            filepath = os.path.join(directory, filename)
            
            # Download the file
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            logging.info(f"Downloading PDF from {url} to {filepath}")
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # Save the file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(filepath)
            file_size_mb = file_size / (1024 * 1024)
            
            logging.info(f"Successfully downloaded {filename} ({file_size_mb:.2f} MB)")
            return {
                "status": "success",
                "filename": filename,
                "filepath": filepath,
                "size": f"{file_size_mb:.2f} MB",
                "url": url
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Download failed for {url}: {e}"
            logging.error(error_msg)
            return {"status": "error", "error": error_msg, "url": url}
        except Exception as e:
            error_msg = f"Unexpected error downloading {url}: {e}"
            logging.error(error_msg)
            return {"status": "error", "error": error_msg, "url": url}

class SeleniumTool(BaseTool):
    name: str = "SeleniumTool"
    description: str = "Crawls a webpage using Selenium and extracts PDF links with their titles."
    driver: Optional[webdriver.Chrome] = Field(default=None, exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.driver = None  # Don't initialize Chrome here

    def _initialize_driver(self):
        """Initialize Chrome driver only when needed"""
        if self.driver is not None:
            return  # Already initialized
            
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in headless mode to prevent Chrome window
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception as e:
            logging.error(f"Failed to initialize Selenium WebDriver: {e}")
            self.driver = None

    def _run(self, url: str) -> List[Dict[str, str]]:
        self._initialize_driver()  # Initialize driver only when needed
        if not self.driver:
            return [{"error": "WebDriver not initialized"}]
        return self.crawl(url)

    def crawl(self, url: str) -> List[Dict[str, str]]:
        if not self.driver:
            self._initialize_driver()
        if not self.driver:
            return [{"error": "WebDriver initialization failed"}]
            
        robots_checker = RobotsTxtCheckerTool()
        if not robots_checker.check(url):
            logging.warning(f"Crawling disallowed by robots.txt for {url}")
            return [{"error": "Crawling disallowed by robots.txt"}]

        logging.info(f"Navigating to {url} with SeleniumTool")
        pdf_links_data = []
        try:
            self.driver.get(url)
            # Increased wait time for page elements to load
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body")) 
            )
            # Allow some extra time for dynamic content
            time.sleep(5)

            # Strategy 1: Find all <a> tags that contain '.pdf' in their href attribute
            elements_strategy1 = self.driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
            logging.info(f"Strategy 1 - Found {len(elements_strategy1)} links with .pdf in href")
            
            # Strategy 2: Find links that mention PDF in the text
            elements_strategy2 = self.driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'PDF', 'pdf'), 'pdf')]")
            logging.info(f"Strategy 2 - Found {len(elements_strategy2)} links mentioning PDF in text")
            
            # Strategy 3: Find links in typical document listing areas
            elements_strategy3 = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'view-content')]//a | //ul[contains(@class, 'field')]//a | //div[contains(@class, 'field')]//a")
            elements_strategy3 = [elem for elem in elements_strategy3 if elem.get_attribute("href") and ('.pdf' in elem.get_attribute("href").lower() or 'pdf' in elem.text.lower())]
            logging.info(f"Strategy 3 - Found {len(elements_strategy3)} PDF links in content areas")

            # Combine all strategies and remove duplicates
            all_elements = elements_strategy1 + elements_strategy2 + elements_strategy3
            unique_hrefs = set()
            unique_elements = []
            
            for element in all_elements:
                href = element.get_attribute("href")
                if href and href not in unique_hrefs and ".pdf" in href.lower():
                    unique_hrefs.add(href)
                    unique_elements.append(element)

            logging.info(f"Total unique PDF links found: {len(unique_elements)}")

            for idx, element in enumerate(unique_elements):
                try:
                    href = element.get_attribute("href")
                    title = element.text.strip()
                    
                    if href and ".pdf" in href.lower():
                        # Ensure the URL is absolute
                        if not href.startswith(('http://', 'https://')):
                            base_url_parts = url.split('/')
                            base_url_domain = f"{base_url_parts[0]}//{base_url_parts[2]}"
                            if href.startswith('/'):
                                href = base_url_domain + href
                            else:
                                href = base_url_domain + '/' + href
                                
                        pdf_data = {"url": href, "title": title if title else f"PDF Document {idx + 1}"}
                        pdf_links_data.append(pdf_data)
                        logging.info(f"Collected PDF {idx + 1}: {pdf_data}")

                except Exception as e:
                    logging.warning(f"Error processing a link element: {e}")
                    continue
            
            if not pdf_links_data:
                logging.warning(f"No PDF links successfully extracted from {url}. Page might not contain direct PDF links or structure changed.")
                # Log some page info for debugging
                logging.info(f"Current page title: {self.driver.title}")
                logging.info(f"Current page URL: {self.driver.current_url}")
                
        except TimeoutException:
            logging.error(f"Timeout waiting for page elements to load on {url}")
            pdf_links_data.append({"error": f"Timeout loading {url}"})
        except Exception as e:
            logging.error(f"An error occurred during crawling {url}: {e}")
            pdf_links_data.append({"error": f"Crawling error on {url}: {str(e)}"})
        
        return pdf_links_data

    def __del__(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            logging.warning(f"Error closing WebDriver: {e}")

class PineconeSearchToolArgs(PydanticBaseModel):
    query: str = Field(description="Search query text")
    top_k: int = Field(default=3, description="Number of results to return")
    score_threshold: float = Field(default=0.5, description="Minimum similarity score threshold (0.0 to 1.0). Default is 0.5.")

class PineconeSearchTool(BaseTool):
    name: str = "PineconeSearchTool"
    description: str = "Search legal documents using semantic search in Pinecone vector database. Requires query, top_k, and score_threshold."
    args_schema: type[PydanticBaseModel] = PineconeSearchToolArgs

    def _run(self, query: str, top_k: int, score_threshold: float) -> List[Dict]:
        # Parameters are now guaranteed by Pydantic model and agent
        final_top_k = top_k
        final_score_threshold = score_threshold
        
        try:
            from setup_pinecone import PineconeVectorStore
            import os
            from dotenv import load_dotenv
            
            load_dotenv()
            PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
            
            if not PINECONE_API_KEY:
                return [{"error": "PINECONE_API_KEY must be set in .env file"}]
            
            vector_store = PineconeVectorStore(api_key=PINECONE_API_KEY)
            
            logging.info(f"PineconeSearchTool: Semantic search for: '{query}', top_k: {final_top_k}, score_threshold: {final_score_threshold}")
            
            results = vector_store.search_similar(
                query=query, 
                top_k=final_top_k, 
                score_threshold=final_score_threshold
            )
            
            if not results:
                return [{"info": f"No relevant documents found matching the criteria (score >= {final_score_threshold}). Consider rephrasing or lowering the threshold."}]
            
            return results
        
        except Exception as e:
            error_msg = f"Error during semantic search: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return [{"error": error_msg}]
            
      