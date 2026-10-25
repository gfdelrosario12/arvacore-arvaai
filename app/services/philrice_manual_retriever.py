"""
Philippine Rice Production Training Manual (PhilRice, 2003) Document Indexer & Retrieval Engine.
Integrates the official 230-page reference manual located in /documentation:
'philippine-rice-production-training-manual.pdf'.

Features:
1. Exact Page-Level Chunking & Text Extraction via PyPDF
2. Cached JSON Index for Fast Deterministic Retrieval (Zero external vector DB dependency)
3. Keyword & Topic-Weighted Search (Land Preparation, Water Management, Seed Selection, AWD, Pests, INM)
4. Source Attribution with exact Page Numbers, Section Headers, and Provenance metadata
"""

import os
import re
import json
from typing import List, Dict, Any, Optional

MANUAL_PDF_PATH = "/home/gladwin/Documents/pagaaral/arvacore/Documentations/philippine-rice-production-training-manual.pdf"
CACHE_INDEX_PATH = "/home/gladwin/Documents/pagaaral/arvacore/ArvaAI/app/services/philrice_manual_index.json"

class PhilRiceManualRetriever:
    def __init__(self, pdf_path: str = MANUAL_PDF_PATH, cache_path: str = CACHE_INDEX_PATH):
        self.pdf_path = pdf_path
        self.cache_path = cache_path
        self.indexed_pages: List[Dict[str, Any]] = []
        self._load_or_build_index()

    def _load_or_build_index(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.indexed_pages = json.load(f)
                    return
            except Exception:
                pass
        
        # Build index from PDF if cache does not exist
        if os.path.exists(self.pdf_path):
            self.build_index()

    def build_index(self) -> int:
        """Parses the PDF and persists the structured page index."""
        try:
            import pypdf
        except ImportError:
            return 0

        if not os.path.exists(self.pdf_path):
            return 0

        reader = pypdf.PdfReader(self.pdf_path)
        pages_data = []

        # Known Module Headers from Table of Contents
        module_titles = {
            15: "Module 1: The Philippine Rice Situation",
            25: "Module 2: Morphology and Growth Stages of the Rice Plant",
            45: "Module 3: Varietal Selection and Seed Quality",
            53: "Module 4: Land Preparation",
            75: "Module 5: Raising Seedlings and Crop Establishment",
            95: "Module 6: Water Management & Irrigation",
            120: "Module 7: Soil Fertility and Nutrient Management",
            155: "Module 8: Weed Management",
            175: "Module 9: Insect Pest and Snail Management",
            205: "Module 10: Harvest and Postharvest Operations"
        }

        current_module = "PhilRice Training Manual"
        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            if page_num in module_titles:
                current_module = module_titles[page_num]

            raw_text = page.extract_text() or ""
            cleaned = re.sub(r"\s+", " ", raw_text).strip()
            
            if len(cleaned) >= 20:
                pages_data.append({
                    "page_number": page_num,
                    "section_header": current_module,
                    "content": cleaned,
                    "char_count": len(cleaned)
                })

        self.indexed_pages = pages_data
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(pages_data, f, indent=2)
        except Exception:
            pass

        return len(pages_data)

    def search_manual(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Executes a deterministic keyword & token-overlap search across the indexed manual.
        Returns top matching passages with exact page numbers.
        """
        if not self.indexed_pages:
            self._load_or_build_index()

        if not self.indexed_pages:
            return []

        tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        if not tokens:
            return []

        scored_results = []
        for p in self.indexed_pages:
            content_lower = p["content"].lower()
            header_lower = p["section_header"].lower()
            
            score = 0
            for t in tokens:
                matches = content_lower.count(t)
                score += matches
                if t in header_lower:
                    score += 5  # Bonus for section header relevance
            
            if score > 0:
                scored_results.append((score, p))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        top_results = []
        for score, p in scored_results[:top_k]:
            # Extract snippet of relevance
            snippet = self._extract_snippet(p["content"], tokens)
            top_results.append({
                "source": "Philippine Rice Production Training Manual (PhilRice, 2003)",
                "page": p["page_number"],
                "section": p["section_header"],
                "relevance_score": score,
                "snippet": snippet
            })

        return top_results

    def _extract_snippet(self, text: str, tokens: List[str], max_len: int = 350) -> str:
        lower = text.lower()
        first_pos = -1
        for t in tokens:
            pos = lower.find(t)
            if pos != -1 and (first_pos == -1 or pos < first_pos):
                first_pos = pos

        if first_pos == -1:
            return text[:max_len] + "..." if len(text) > max_len else text

        start = max(0, first_pos - 80)
        end = min(len(text), start + max_len)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

