import pytest
from urllib.parse import urlparse
from email_spider import prioritize_links

# Mock link object for testing
class Link:
    def __init__(self, url):
        self.url = url


def test_full_word_match_priority():
    """Test that full word matches are prioritized over partial matches"""
    links = [
        Link('https://example.com/network'),
        Link('https://example.com/about')
    ]
    priority_keywords = ['work', 'about']
    
    result = prioritize_links(links, priority_keywords)
    
    # /about should come first (full word match for 'about')
    # /network should come second (partial match for 'work')
    assert result[0].url == 'https://example.com/about'
    assert result[1].url == 'https://example.com/network'


def test_keyword_position_priority():
    """Test that earlier keywords in list have higher priority"""
    links = [
        Link('https://example.com/contact'),
        Link('https://example.com/about')
    ]
    priority_keywords = ['about', 'contact']
    
    result = prioritize_links(links, priority_keywords)
    
    # /about should come first (index 0 in priority list)
    assert result[0].url == 'https://example.com/about'
    assert result[1].url == 'https://example.com/contact'


def test_hyphenated_urls():
    """Test that hyphens are treated as word boundaries"""
    links = [
        Link('https://example.com/network-systems'),
        Link('https://example.com/work-life')
    ]
    priority_keywords = ['work', 'network']
    
    result = prioritize_links(links, priority_keywords)
    
    # /work-life should come first (full word match for 'work')
    # /network-systems should come second (full word match for 'network')
    assert result[0].url == 'https://example.com/work-life'
    assert result[1].url == 'https://example.com/network-systems'


def test_no_keyword_match():
    """Test that URLs without keyword matches have lowest priority"""
    links = [
        Link('https://example.com/random'),
        Link('https://example.com/about'),
        Link('https://example.com/other')
    ]
    priority_keywords = ['about', 'work']
    
    result = prioritize_links(links, priority_keywords)
    
    # /about should come first
    # /random and /other should come after (order between them doesn't matter)
    assert result[0].url == 'https://example.com/about'
    assert result[1].url in ['https://example.com/random', 'https://example.com/other']
    assert result[2].url in ['https://example.com/random', 'https://example.com/other']


def test_case_insensitivity():
    """Test that keyword matching is case-insensitive"""
    links = [
        Link('https://example.com/About'),
        Link('https://example.com/WORK')
    ]
    priority_keywords = ['work', 'about']
    
    result = prioritize_links(links, priority_keywords)
    
    # Both should match, with 'work' having higher priority
    assert result[0].url == 'https://example.com/WORK'
    assert result[1].url == 'https://example.com/About'


def test_partial_vs_full_match_same_keyword():
    """Test that full match beats partial match for same keyword"""
    links = [
        Link('https://example.com/network'),
        Link('https://example.com/work')
    ]
    priority_keywords = ['work']
    
    result = prioritize_links(links, priority_keywords)
    
    # /work should come first (full word match)
    # /network should come second (partial match)
    assert result[0].url == 'https://example.com/work'
    assert result[1].url == 'https://example.com/network'


def test_multiple_keywords_in_path():
    """Test that only first matching keyword determines priority"""
    links = [
        Link('https://example.com/about/contact'),
        Link('https://example.com/work')
    ]
    priority_keywords = ['work', 'about']
    
    result = prioritize_links(links, priority_keywords)
    
    # /work should come first (index 0 in priority list)
    # /about/contact should come second (index 1 in priority list)
    assert result[0].url == 'https://example.com/work'
    assert result[1].url == 'https://example.com/about/contact'


def test_slash_boundaries():
    """Test that slashes act as word boundaries"""
    links = [
        Link('https://example.com/about/'),
        Link('https://example.com/aboutus')
    ]
    priority_keywords = ['about']
    
    result = prioritize_links(links, priority_keywords)
    
    # /about/ should come first (full word match)
    # /aboutus should come second (partial match)
    assert result[0].url == 'https://example.com/about/'
    assert result[1].url == 'https://example.com/aboutus'


def test_empty_links():
    """Test that empty list returns empty list"""
    links = []
    priority_keywords = ['work', 'about']
    
    result = prioritize_links(links, priority_keywords)
    
    assert result == []


def test_empty_keywords():
    """Test that empty keywords list puts all links at same priority"""
    links = [
        Link('https://example.com/about'),
        Link('https://example.com/work')
    ]
    priority_keywords = []
    
    result = prioritize_links(links, priority_keywords)
    
    # All should have same priority, order doesn't matter but length should match
    assert len(result) == 2