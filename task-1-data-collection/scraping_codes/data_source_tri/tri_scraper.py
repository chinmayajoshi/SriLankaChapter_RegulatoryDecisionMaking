"""
Original code by Memoona in https://colab.research.google.com/drive/
1Jvf4Z2-mxKMvemg6GaxRuD53WPVnOFJD#scrollTo=CY4ndzlUsulN

This files scrapes Circulars and Guidelines from
https://www.tri.lk/view-all-publications/ using playwright, BeautifulSoup,
and requests, and saves the downloads in the relevant data folder.

Sample usage:
result = await scrape_website('https://www.tri.lk/view-all-publications/',
'data/task1_raw_input/data_source_tri/v0_0/files/')
"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import requests
import os
import csv


def write_to_csv(contents, destination_file_relative_path):
    script_path = os.path.dirname(__file__)
    output_csv = os.path.join(script_path, destination_file_relative_path)
    field_names = [
        "class",
        "filename",
        "path",
        "url",
        "data_origin",
        "retrieved_date_of_issuance",
        "issuing_authority",
        "retrieved_topic",
        "PDF_or_text",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()  # Write the header row
        writer.writerows(contents)  # Write the data rows


def trim_absolute_path_tri(file_path):
    trimmed_path = None
    file_path_mod = file_path.split("SriLankaChapter_RegulatoryDecisionMaking")
    e = "\\task-1-data-collection\\scraping_codes\\data_source_tri\\..\\..\\.."
    if len(file_path_mod) > 1:
        trimmed_path = file_path_mod[1].replace(e, "")
    return trimmed_path


def download_pdf_and_get_info(publications, destination_folder):
    """
    Uses the requests library to download pdfs from the links given.
    Args:
        publications: A list of dictionaries, each containing PDF Name,
        PDF Link, and Publication Date.
        destination_folder: Relative path to the folder where you want the
        scraped result to be stored.
    Returns:
        A list of dictionaries containing PDF Names and Publication Dates
        and other information.
    """
    results = []
    # Counter dictionary to keep track of filenames
    counter = {}
    for pub in publications:
        request_url = pub["PDF Link"]
        if not request_url.startswith("https://www.tri.lk"):
            request_url = "https://www.tri.lk" + pub["PDF Link"]

        response = requests.get(request_url)

        if response.status_code == 200:
            # Extracting the filename from the URL
            pdf_name = request_url.split("/")[-1]

            # Increment counter for duplicate filenames
            if pdf_name in counter:
                counter[pdf_name] += 1
                # Append the counter before .pdf
                pdf_name = f"{pdf_name[:-4]} - {counter[pdf_name]}.pdf"
            else:
                counter[pdf_name] = 1

            # Save the PDF
            destination_class_folder = os.path.join(
                destination_folder, pub["PDF Class"]
            )
            os.makedirs(destination_class_folder, exist_ok=True)
            pdf_path = os.path.join(destination_class_folder, pdf_name)
            with open(pdf_path, "wb") as f:
                f.write(response.content)

            # Use Beautiful Soup to scrape the page for additional info
            # soup = BeautifulSoup(response.content, 'html.parser')
            # Here you would define how to find publication date and other info
            # Assuming publication date is in a specific tag (modify as needed)
            #  - this was not working so commented
            # publication_date = (soup.find('meta', {'name': 'date'})
            # ['content'] if soup.find('meta', {'name': 'date'}) else '')

            trimmed_path = trim_absolute_path_tri(pdf_path)
            if pdf_name:
                results.append(
                    {
                        "class": pub["PDF Class"],
                        "filename": pdf_name,
                        "path": trimmed_path,
                        "url": request_url,
                        "data_origin": "scraped",
                        "retrieved_date_of_issuance": pub["Publication Date"],
                        "issuing_authority": "TRI " + pub["PDF Class"],
                        "retrieved_topic": pub["PDF Name"],
                        "PDF_or_text": "PDF",
                    }
                )
        else:
            print(f"Failed to retrieve {request_url}")

    # Note: This path for the csv is hardcoded now,
    # it should be fixed to work for v0_1
    write_to_csv(
        results,
        os.path.join(
            "..\\..\\..\\data\\task1_raw_input\\",
            "data_source_tri\\v0_0\\v0_0_LK_tea_tri_raw.csv",
        ),
    )
    return results


async def get_pdf_links(tri_url):
    """
    Scrapes the specified website asynchronously and returns the scraped data.
    Args:
        url (str): The URL of the website to scrape.
    Returns:
        list: A list of dictionaries containing the PDF Name, PDF Link,
        Publication Date, and PDF class of Circulers or Guideline.
    """
    async with async_playwright() as p:
        # Launch a headless browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        table_selectors = [
            "table#footable_581",  # Circulars Table
            "table#footable_616",
        ]  # Guidelines Table

        # next selector
        nxt_sel = 'li.footable-page-nav[data-page="next"] a.footable-page-link'

        publications = []
        current_page = tri_url
        print(f"Scraping page: {current_page}")
        await page.goto(current_page)
        await page.wait_for_timeout(5000)  # Adjust time as needed for loading

        for table_selector in table_selectors:
            if table_selector == "table#footable_581":
                document_class = "Circulers"
            elif table_selector == "table#footable_616":
                document_class = "Guideline"
            # last_table_html is a workaround to check when there are
            # no more Next pages and exit the pagination loop
            last_table_html = ""
            while True:
                # Get the table content
                current_table_html = await page.inner_html(table_selector)
                # Check if the table content has changed
                if current_table_html == last_table_html:
                    # Table content is the same as the previous iteration,
                    # no more Next pages, exit the loop
                    break
                last_table_html = current_table_html

                # Use BeautifulSoup to parse the HTML
                soup = BeautifulSoup(current_table_html, "html.parser")

                # Extract all PDF links, names, and publication dates
                for row in soup.find_all("tr"):
                    link_tag = row.find("a", href=True)
                    date_tag = row.find("td", class_="ninja_clmn_nm_issued_in")

                    if link_tag and date_tag:
                        pdf_link = link_tag["href"]  # PDF link
                        pdf_name = link_tag.text.strip()  # PDF name
                        pdf_date = date_tag.text.strip()  # PDF date

                        publications.append(
                            {
                                "PDF Name": pdf_name,
                                "PDF Link": pdf_link,
                                "Publication Date": pdf_date,
                                "PDF Class": document_class,
                            }
                        )

                # Check if there is a "Next" button to go to the next page
                next_button = await page.query_selector(nxt_sel)
                if next_button:
                    await next_button.click()
                    # Wait for the new page content to load
                    await page.wait_for_timeout(2000)
                else:
                    # No Next button found
                    break  # exit the pagination loop

        # Close the browser
        await browser.close()

        return publications


async def scrape_website(tri_url, destination_data_folder):
    """
    Scrapes the specified website asynchronously and returns the scraped data.
    Args:
        url (str): The URL of the website to scrape.
        destination_data_folder: path to the folder where you want the
        scraped result to be stored.
    Returns:
        dict: A list of dictionaries containing PDF Names and Publication
        Dates. Also, pdf files are saved into the destination_data_folder.
    Sample:
        res = await scrape_website('https://www.tri.lk/view-all-publications/',
          'data/task1_raw_input/data_source_tri/v0_0/files/')
    """
    # Create the relative path to the destination data folder
    script_path = os.path.dirname(__file__)
    relative_path_to_root = os.path.join(script_path, "..\\..\\..\\")
    destination_folder = os.path.join(relative_path_to_root, destination_data_folder)

    # Scrape the PDF links from the TRI website
    result = await get_pdf_links(tri_url)
    print(f"Number of results: {len(result)}")
    print(f"Initial scraping done. Downloading into {destination_folder}")

    # Download the documents from the links that were scraped
    downloaded_results = download_pdf_and_get_info(result, destination_folder)
    print("Downloaded documents from TRI")

    return downloaded_results


async def main():
    res = await scrape_website(
        "https://www.tri.lk/view-all-publications/",
        "data\\task1_raw_input\\data_source_tri\\v0_0\\files\\",
    )
    print(res)


# Entry point for the script
if __name__ == "__main__":
    asyncio.run(main())
    # Instead of asyncio.run, use the following within a
    # Jupyter/IPython environment:
    # await run()  # This uses the existing event loop of the environment
