import os
import re
from typing import Any, Dict, Iterator, List, Optional, Union  # Corrected imports

import pypdf
from pypdf import PdfReader
from pypdf.generic import Destination

from langchain.document_loaders.parsers.pdf import PyPDFParser
from langchain.document_loaders.blob_loaders import Blob
from langchain.schema import Document

from collections import defaultdict  # Keep if needed elsewhere, removed from core logic


class PyPDFOutlineParser(PyPDFParser):
    """
    A PDF parser that extracts text based on PDF outlines (bookmarks),
    assigning the text of page ranges to the corresponding sections.

    Note: This parser assigns the text of full pages to sections. If multiple
    bookmarks point to the same page, the text of that page might be included
    in multiple sections depending on the calculated ranges. It does not split
    text *within* a single page based on bookmark locations.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Removes or replaces characters invalid for filenames."""
        name = str(name)  # Ensure string
        # Remove invalid characters specific to most file systems
        name = re.sub(r'[\\/*?:"<>|]', "", name)
        # Replace sequences of whitespace with a single underscore
        name = re.sub(r"\s+", "_", name)
        # Truncate long filenames if necessary (e.g., 200 chars)
        name = name[:200]
        if not name:
            name = "Untitled_Section"
        return name

    @staticmethod
    def gather_bookmarks_recursive(
        bookmark_list: List[Any],
        reader: PdfReader,
        parent_title: str = "",
        level: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Recursively traverses the bookmark structure.
        Returns a flat list of bookmark details.
        """
        results = []
        current_parent_title_for_list = ""

        for item in bookmark_list:
            if isinstance(item, pypdf.generic.Destination):
                # Store this title in case the *next* item is a list (its children)
                current_parent_title_for_list = item.title
                try:
                    page_index = reader.get_destination_page_number(item)
                    page_label = ""
                    # Page labels might not exist or cover all pages
                    if reader.page_labels and page_index < len(reader.page_labels):
                        page_label = reader.page_labels[
                            page_index
                        ]  # Can still fail if mapping is complex

                    result = {
                        "section_title": item.title,
                        "page_label": page_label,  # The label for the page (e.g., 'iii', '5')
                        "page_index": page_index,  # 0-based index
                        "parent_section": parent_title,  # Title of the parent bookmark
                        "level": level,  # Depth in the outline tree
                    }
                    results.append(result)
                except Exception as e:
                    print(
                        f"Warning: Could not process bookmark '{getattr(item,'title','Unknown')}'. Skipping. Error: {e}"
                    )

            elif isinstance(item, list):
                # Recursive call for nested bookmarks
                # Use the title of the Destination that *preceded* this list as the parent
                results.extend(
                    PyPDFOutlineParser.gather_bookmarks_recursive(
                        item,
                        reader,
                        parent_title=current_parent_title_for_list,
                        level=level + 1,
                    )
                )
        return results

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob based on PDF outlines."""
        try:
            with blob.as_bytes_io() as pdf_file_obj:
                reader = pypdf.PdfReader(pdf_file_obj, password=self.password)
                total_pages = len(reader.pages)

                if not reader.outline:
                    print(
                        "Warning: PDF has no outlines (bookmarks). Falling back to default page-by-page parsing."
                    )
                    # Optionally fall back to parent's behavior or yield page-by-page
                    # For now, just yield nothing from this parser if no outlines
                    return iter([])  # Return empty iterator

                # --- 1. Get Flattened List of All Bookmarks ---
                all_bookmarks = self.gather_bookmarks_recursive(reader.outline, reader)

                if not all_bookmarks:
                    print(
                        "Warning: No bookmarks found in the PDF outline. Falling back to default page-by-page parsing."
                    )
                    # Optionally fall back to parent's behavior or yield page-by-page
                    # For now, just yield nothing from this parser if no bookmarks
                    return iter([])

                if not all_bookmarks:
                    print("Warning: No valid bookmarks could be extracted.")
                    return iter([])  # Return empty iterator

                # --- 2. Sort Bookmarks by Page Index ---
                # This is crucial for determining page ranges correctly
                all_bookmarks.sort(key=lambda x: x["page_index"])

                print(f"Found {len(all_bookmarks)} bookmarks to process.")

                # --- 3. Iterate Through Bookmarks to Define Sections and Extract Text ---
                for i, current_bookmark in enumerate(all_bookmarks):
                    start_page_index = current_bookmark["page_index"]

                    # Determine end page index
                    if i + 1 < len(all_bookmarks):
                        next_bookmark_page_index = all_bookmarks[i + 1]["page_index"]
                        # End page is the one *before* the next bookmark starts
                        end_page_index = next_bookmark_page_index - 1
                    else:
                        # This is the last bookmark, section goes to the end of the PDF
                        end_page_index = total_pages - 1

                    # Ensure end_page is not before start_page (e.g., multiple bookmarks on same page)
                    end_page_index = max(start_page_index, end_page_index)

                    # --- 4. Extract Text for the Calculated Page Range ---
                    section_text_parts = []
                    # print(f"  Extracting '{current_bookmark['section_title']}': Pages {start_page_index + 1}-{end_page_index + 1}") # Debug print
                    for page_num in range(start_page_index, end_page_index + 1):
                        if 0 <= page_num < total_pages:
                            try:
                                page_text = reader.pages[page_num].extract_text()
                                if page_text:
                                    section_text_parts.append(page_text)
                            except Exception as e:
                                print(
                                    f"Warning: Failed to extract text from page index {page_num}. Error: {e}"
                                )
                        else:
                            print(
                                f"Warning: Page index {page_num} out of bounds (0-{total_pages-1})."
                            )

                    full_section_text = "\n".join(section_text_parts).strip()

                    # --- 5. Prepare Metadata ---
                    metadata = current_bookmark.copy()  # Use bookmark details as base
                    metadata["source"] = (
                        blob.source if hasattr(blob, "source") else "unknown"
                    )
                    metadata["page"] = metadata[
                        "page_index"
                    ]  # Langchain often uses 'page' for 0-index
                    metadata["start_page_index"] = (
                        start_page_index  # Explicitly add range
                    )
                    metadata["end_page_index"] = end_page_index  # Explicitly add range
                    # Optional: Create a potential filename (useful for some downstream tasks)
                    # metadata["filename_section"] = self._sanitize_filename(current_bookmark['section_title']) + ".txt"

                    # --- 6. Yield Document ---
                    if full_section_text:  # Only yield if text was actually extracted
                        yield Document(
                            page_content=full_section_text, metadata=metadata
                        )
                    else:
                        print(
                            f"  Skipping section '{current_bookmark['section_title']}' due to empty text content."
                        )  # Debug print

        except Exception as e:
            print(f"Error parsing PDF blob: {e}")
            # Decide if you want to raise the error or yield nothing
            raise e
