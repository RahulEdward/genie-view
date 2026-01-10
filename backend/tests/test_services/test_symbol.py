"""
Symbol Service Tests
Property-based and unit tests for symbol search
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.services.symbol import search_symbols_fuzzy


# ==================== Property Tests ====================

class TestSymbolSearchRelevance:
    """
    Property 17: Symbol Search Relevance
    For any search query, results SHALL contain the query string and all required fields.
    Validates: Requirements 12.1, 12.4, 12.5
    """
    
    @given(
        st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
                "name": st.text(min_size=1, max_size=50),
                "token": st.text(min_size=1, max_size=10),
                "exchange": st.sampled_from(["NSE", "BSE", "NFO", "BFO"]),
            }),
            min_size=0,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_results_contain_query(self, query: str, symbols: list):
        """
        Property: All search results contain the query string in symbol or name.
        """
        results = search_symbols_fuzzy(query, symbols)
        
        query_upper = query.upper()
        for result in results:
            symbol_upper = result.get("symbol", "").upper()
            name_upper = result.get("name", "").upper()
            
            assert query_upper in symbol_upper or query_upper in name_upper, \
                f"Query '{query}' not found in result: {result}"
    
    @given(
        st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=30),
                "name": st.text(min_size=1, max_size=50),
                "token": st.text(min_size=1, max_size=10),
                "exchange": st.sampled_from(["NSE", "BSE", "NFO"]),
            }),
            min_size=0,
            max_size=50
        ),
        st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100)
    def test_results_respect_limit(self, query: str, symbols: list, limit: int):
        """
        Property: Number of results never exceeds the limit.
        """
        results = search_symbols_fuzzy(query, symbols, limit=limit)
        
        assert len(results) <= limit
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=30),
                "name": st.text(min_size=1, max_size=50),
                "token": st.text(min_size=1, max_size=10),
                "exchange": st.sampled_from(["NSE", "BSE"]),
            }),
            min_size=0,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_required_fields_present(self, symbols: list):
        """
        Property: All results have required fields.
        """
        # Search with a common letter
        results = search_symbols_fuzzy("A", symbols)
        
        required_fields = {"symbol", "name", "token", "exchange"}
        
        for result in results:
            assert required_fields.issubset(result.keys()), \
                f"Missing fields: {required_fields - set(result.keys())}"
    
    @given(
        st.text(min_size=3, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',))),
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Lu',))),
                "name": st.text(min_size=1, max_size=50),
            }),
            min_size=5,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_exact_match_ranked_first(self, query: str, symbols: list):
        """
        Property: Exact symbol match is ranked first.
        """
        # Add an exact match
        exact_match = {"symbol": query.upper(), "name": "Exact Match", "token": "123", "exchange": "NSE"}
        symbols_with_exact = symbols + [exact_match]
        
        results = search_symbols_fuzzy(query, symbols_with_exact)
        
        if results:
            # If exact match exists, it should be first
            if any(s["symbol"].upper() == query.upper() for s in symbols_with_exact):
                assert results[0]["symbol"].upper() == query.upper(), \
                    f"Exact match should be first, got: {results[0]['symbol']}"


class TestSearchOrdering:
    """Test search result ordering"""
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.sampled_from(["RELIANCE", "RELIANCEINF", "RELCAPITAL", "TCS", "INFY"]),
                "name": st.text(min_size=1, max_size=50),
            }),
            min_size=3,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_starts_with_ranked_higher(self, symbols: list):
        """
        Property: Symbols starting with query ranked higher than containing.
        """
        results = search_symbols_fuzzy("REL", symbols)
        
        if len(results) >= 2:
            # Check that "starts with" matches come before "contains" matches
            starts_with_indices = [
                i for i, r in enumerate(results) 
                if r["symbol"].upper().startswith("REL")
            ]
            contains_indices = [
                i for i, r in enumerate(results) 
                if "REL" in r["symbol"].upper() and not r["symbol"].upper().startswith("REL")
            ]
            
            if starts_with_indices and contains_indices:
                assert max(starts_with_indices) < min(contains_indices), \
                    "Starts-with matches should come before contains matches"


# ==================== Unit Tests ====================

class TestSearchSymbolsFuzzy:
    """Unit tests for fuzzy search"""
    
    def test_exact_match(self):
        """Exact symbol match returns result"""
        symbols = [
            {"symbol": "RELIANCE", "name": "Reliance Industries", "token": "2885", "exchange": "NSE"},
            {"symbol": "TCS", "name": "Tata Consultancy", "token": "11536", "exchange": "NSE"},
        ]
        
        results = search_symbols_fuzzy("RELIANCE", symbols)
        
        assert len(results) == 1
        assert results[0]["symbol"] == "RELIANCE"
    
    def test_partial_match(self):
        """Partial symbol match returns results"""
        symbols = [
            {"symbol": "RELIANCE", "name": "Reliance Industries", "token": "2885", "exchange": "NSE"},
            {"symbol": "RELIANCEINF", "name": "Reliance Infra", "token": "1234", "exchange": "NSE"},
            {"symbol": "TCS", "name": "Tata Consultancy", "token": "11536", "exchange": "NSE"},
        ]
        
        results = search_symbols_fuzzy("REL", symbols)
        
        assert len(results) == 2
        assert all("REL" in r["symbol"] for r in results)
    
    def test_case_insensitive(self):
        """Search is case insensitive"""
        symbols = [
            {"symbol": "RELIANCE", "name": "Reliance Industries", "token": "2885", "exchange": "NSE"},
        ]
        
        results_upper = search_symbols_fuzzy("RELIANCE", symbols)
        results_lower = search_symbols_fuzzy("reliance", symbols)
        results_mixed = search_symbols_fuzzy("Reliance", symbols)
        
        assert len(results_upper) == len(results_lower) == len(results_mixed) == 1
    
    def test_name_search(self):
        """Search matches name field"""
        symbols = [
            {"symbol": "RELIANCE", "name": "Reliance Industries", "token": "2885", "exchange": "NSE"},
            {"symbol": "TCS", "name": "Tata Consultancy Services", "token": "11536", "exchange": "NSE"},
        ]
        
        results = search_symbols_fuzzy("Industries", symbols)
        
        assert len(results) == 1
        assert results[0]["symbol"] == "RELIANCE"
    
    def test_no_match(self):
        """No match returns empty list"""
        symbols = [
            {"symbol": "RELIANCE", "name": "Reliance Industries", "token": "2885", "exchange": "NSE"},
        ]
        
        results = search_symbols_fuzzy("NONEXISTENT", symbols)
        
        assert len(results) == 0
    
    def test_limit_respected(self):
        """Limit parameter is respected"""
        symbols = [
            {"symbol": f"TEST{i}", "name": f"Test {i}", "token": str(i), "exchange": "NSE"}
            for i in range(20)
        ]
        
        results = search_symbols_fuzzy("TEST", symbols, limit=5)
        
        assert len(results) == 5
    
    def test_empty_symbols_list(self):
        """Empty symbols list returns empty results"""
        results = search_symbols_fuzzy("TEST", [])
        
        assert len(results) == 0
    
    def test_relevance_ordering(self):
        """Results are ordered by relevance"""
        symbols = [
            {"symbol": "RELIANCEINF", "name": "Reliance Infra", "token": "1", "exchange": "NSE"},
            {"symbol": "RELIANCE", "name": "Reliance Industries", "token": "2", "exchange": "NSE"},
            {"symbol": "RELCAPITAL", "name": "Reliance Capital", "token": "3", "exchange": "NSE"},
        ]
        
        results = search_symbols_fuzzy("RELIANCE", symbols)
        
        # Exact match should be first
        assert results[0]["symbol"] == "RELIANCE"
