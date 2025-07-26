"""
PDF document processor.

This module handles PDF document processing.
"""

from typing import Any

import pypdf


class PDFProcessor:
    """Processes PDF documents."""

    def process(self, file_path: str) -> dict[str, Any]:
        """Process a PDF file and extract its content."""
        try:
            with open(file_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)

                text_content = ""
                page_count = len(pdf_reader.pages)

                for _page_num, page in enumerate(pdf_reader.pages):
                    text_content += page.extract_text() + "\n"

                return {
                    "text": text_content,
                    "page_count": page_count,
                    "file_path": file_path,
                }
        except Exception as e:
            raise Exception(f"Error processing PDF: {str(e)}")
