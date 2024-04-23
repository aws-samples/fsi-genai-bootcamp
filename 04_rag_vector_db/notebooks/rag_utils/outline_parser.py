from langchain.document_loaders.parsers.pdf import PyPDFParser
from langchain.document_loaders.blob_loaders import Blob
from langchain.schema import Document

from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Union,
    Dict,
)

from itertools import groupby, zip_longest
from operator import itemgetter
from collections import defaultdict
import re
import pypdf
from pypdf import PdfReader


class PyPDFOutlineParser(PyPDFParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def gather_bookmarks(
        bookmark_list, reader: PdfReader, parent_title: str = "", nested: bool = False
    ) -> Dict[Union[str, int], str]:
        results = []
        for n, item in enumerate(bookmark_list):
            if isinstance(item, list):
                parent_title = bookmark_list[n - 1].title
                results.extend(
                    PyPDFOutlineParser.gather_bookmarks(
                        item, reader, parent_title, nested=True
                    )
                )
            else:
                page_index = reader.get_destination_page_number(item)
                page_label = reader.page_labels[page_index]

                if not nested:
                    parent_title = ""

                result = {
                    "section_title": item.title,
                    "page_label": page_label,
                    "page_index": page_index,
                    "parent_section": parent_title,
                }

                results.append(result)

        return results

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob."""

        with blob.as_bytes_io() as pdf_file_obj:
            pdf_reader = pypdf.PdfReader(pdf_file_obj, password=self.password)
            bookmarks = self.gather_bookmarks(pdf_reader.outline, pdf_reader)

            page_sections = defaultdict(list)

            for page, sections in groupby(bookmarks, key=itemgetter("page_index")):
                for section in sections:
                    page_sections[page].append(section)

            page_nums = sorted(page_sections.keys())

            for page_num, next_page_num in zip_longest(page_nums, page_nums[1:]):
                sections = page_sections[page_num]

                page_text = pdf_reader.pages[page_num].extract_text()
                # extract text between section titles
                for section, next_section in zip_longest(sections, sections[1:]):
                    title = section["section_title"]
                    next_title = next_section["section_title"] if next_section else None

                    if next_title is None:
                        section_text = re.search(f"{title}(.*)", page_text, re.DOTALL)

                        if section_text is not None:
                            section_text = section_text.group(1)
                        else:
                            section_text = ""

                        if next_page_num is not None:
                            next_page_section_title = page_sections[next_page_num][0][
                                "section_title"
                            ]

                            for p in range(page_num + 1, next_page_num + 1):
                                page_text = pdf_reader.pages[p].extract_text()
                                next_title_in_text = re.search(
                                    f"(.*){next_page_section_title}",
                                    page_text,
                                    re.DOTALL,
                                )
                                if next_title_in_text is not None:
                                    section_text += f"\n{next_title_in_text.group(1)}"
                                else:
                                    section_text += f"\n{page_text}"

                    else:
                        section_text = re.search(
                            f"{title}(.*){next_title}", page_text, re.DOTALL
                        )

                        if section_text:
                            section_text = section_text.group(1)
                        else:
                            section_text = page_text

                    yield Document(page_content=section_text, metadata=section)
