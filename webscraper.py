import os
import logging
import json
from urllib.parse import urlparse
from crewai import Crew
from crewai.tasks.task_output import TaskOutput
from agents import scraper
from tasks import scrape_task
from tools import RequestsTool

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PDF_DOWNLOAD_DIR = "data/pdfs"

def download_pdfs_from_list(pdf_info_list: list):
    if not isinstance(pdf_info_list, list):
        logging.error(f"Expected a list of PDFs, but got: {type(pdf_info_list)}")
        return 0

    os.makedirs(PDF_DOWNLOAD_DIR, exist_ok=True)
    downloader = RequestsTool()
    downloaded_count = 0
    failed_count = 0

    logging.info(f"Found {len(pdf_info_list)} PDF links to download.")

    for i, pdf_info in enumerate(pdf_info_list):
        if not isinstance(pdf_info, dict) or 'url' not in pdf_info or 'title' not in pdf_info:
            logging.warning(f"Skipping invalid PDF info item: {pdf_info}")
            failed_count += 1
            continue

        url = pdf_info['url']
        title = pdf_info['title']
        # Sanitize title to create a filename
        filename_base = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title).strip()
        if not filename_base:
            filename_base = os.path.basename(urlparse(url).path).replace('.pdf', '')
        filename = f"{filename_base}.pdf"

        logging.info(f"Downloading PDF {i+1}/{len(pdf_info_list)}: '{title}' from {url}")
        try:
            download_result = downloader.download_pdf(url=url, filename=filename, directory=PDF_DOWNLOAD_DIR)
            if download_result.get("status") == "success":
                logging.info(f"  ✅ Success: {download_result.get('filename')} ({download_result.get('size')})")
                downloaded_count += 1
            else:
                logging.error(f"  ❌ Failed to download {url}: {download_result.get('error')}")
                failed_count += 1
        except Exception as e:
            logging.error(f"  ❌ Exception while downloading {url}: {e}")
            failed_count += 1
            
    logging.info(f"Download process complete. Successfully downloaded: {downloaded_count}, Failed: {failed_count}")
    return downloaded_count


if __name__ == "__main__":
    scrape_task.agent = scraper

    crew = Crew(
        agents=[scraper],
        tasks=[scrape_task],
        verbose=1
    )
    
    print("📄 Starting USCIS PDF Link Extraction Process...")
    print("=" * 60)
    
    crew_result = crew.kickoff()
    
    print("\n" + "=" * 60)
    print("🔗 PDF LINKS EXTRACTION REPORT:")
    print("=" * 60)

    pdf_links = []

    if crew_result:
        # Get the agent output from the task result
        if hasattr(crew_result, 'tasks_output') and crew_result.tasks_output:
            task_output_obj: TaskOutput = crew_result.tasks_output[0]
            agent_output_str = str(task_output_obj)
        else:
            agent_output_str = str(crew_result)

        # Parse the JSON output from the agent
        if isinstance(agent_output_str, str):
            cleaned_output = agent_output_str.strip()
            if cleaned_output.startswith("[") and cleaned_output.endswith("]"):
                try:
                    # Replace single quotes with double quotes for valid JSON
                    valid_json_str = cleaned_output.replace("'", '"')
                    pdf_links = json.loads(valid_json_str)
                    logging.info(f"Successfully parsed agent output with {len(pdf_links)} PDF links")
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse agent output as JSON: {e}")
                    pdf_links = []
        elif isinstance(agent_output_str, list):
            pdf_links = agent_output_str
    else:
        logging.error("Crew kickoff returned no result.")

    # Filter valid PDF info
    valid_pdf_infos = [info for info in pdf_links if isinstance(info, dict) and 'url' in info and 'title' in info]

    if valid_pdf_infos:
        print(f"✅ Agent extracted {len(valid_pdf_infos)} PDF links.")
        print("\n" + "=" * 60)
        print("📥 Starting PDF Download Process...")
        print("=" * 60)
        downloaded_count = download_pdfs_from_list(valid_pdf_infos)
        print("=" * 60)
        print(f"🏁 Download process finished. {downloaded_count} PDFs downloaded to {PDF_DOWNLOAD_DIR}.")
    else:
        print("❌ Agent did not return any valid PDF links to download.")
        print("=" * 60)
        print("🏁 Process completed with no PDFs to download.")
