from collections import defaultdict
import scrapy
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urlparse, urlunparse

class EmailSpider(scrapy.Spider):
    name = 'email_spider'

    def __init__(self, start_urls, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Split the comma-separated start URLs into a list
        if isinstance(start_urls, str):
            self.start_urls = start_urls.split(',')
        else:
            self.start_urls = start_urls
        
        self.start_urls = ensure_urls_valid(self.start_urls)

        # Use default values that will be overridden by from_crawler()
        self.max_pages_per_domain = 50
        self.priority_url_keywords = []

        # Set to store already found emails
        self.found_emails = set()

         # Counter to track pages crawled per domain
        self.pages_crawled_per_domain = defaultdict(int)

    def parse(self, response):
        current_domain = domain(response.url)

        # Use the efficient email extraction function, 
        # NOTE: regex is very slow against whole response
        emails = extract_emails(response.text, current_domain)
        
        # Only yield emails that haven't been found yet
        for email in emails:
            if email not in self.found_emails:
                self.found_emails.add(email)
                yield { 'email': email }

        # Increment the counter for this domain
        self.pages_crawled_per_domain[current_domain] += 1

        # Follow links only if we haven't reached the max pages for this domain
        if self.pages_crawled_per_domain[current_domain] > self.max_pages_per_domain:
            return 
        
        # Follow links only from the start pages (depth 0)
        if response.meta.get('depth', 0) == 0:
            le = LinkExtractor(
                # Avoid crawling external links e.g. youtube
                allow_domains=[current_domain], 
                # Avoid duplicate crawling of already visited pages
                process_value=remove_fragment,
            )
            links = le.extract_links(response)
            
            # Prioritize links containing keywords
            prioritized_links = prioritize_links(links, self.priority_url_keywords)
            
            # How many requests we could send to this domain
            links_limit = self.max_pages_per_domain - self.pages_crawled_per_domain[current_domain]
            
            for index, link in enumerate(prioritized_links[:links_limit]):
                yield scrapy.Request(
                    link.url,
                    callback=self.parse,
                    priority=len(prioritized_links) - index  # higher for earlier links
                )


    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        # Set these attributes after the spider is created
        spider.max_pages_per_domain = crawler.settings.get('MAX_PAGES_PER_DOMAIN', 50)
        spider.priority_url_keywords = crawler.settings.get('PRIORITY_URL_KEYWORDS', [])
        return spider

def domain(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc

def remove_fragment(url):
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=''))

def ensure_urls_valid(urls):
    # Avoid missing scheme errors
    valid_urls = []
    for url in urls:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url  # Assume HTTPS by default
        valid_urls.append(url)
    return valid_urls

def prioritize_links(links, priority_keywords):
    """Sort links based on highest priority keyword found in the URL path.
    
    1. Only checks the URL path for the first matching keyword.
    2. Priority is based on the keyword position in the priority_keywords list.
    3. URLs whose paths don't match any keyword have the lowest priority.
    """
    def priority_score(link):
        path = urlparse(link.url).path.lower()
        for index, keyword in enumerate(priority_keywords):
            if keyword.lower() in path:
                # Lower index means higher priority
                return index
        # If no keywords match, return a value higher than any index
        return len(priority_keywords) + 1
    
    return sorted(links, key=priority_score)

def extract_emails(text, domain):
    target = "@" + domain.replace('www.', '')
    # Allowed characters for the email username (based on [\w\.-])
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    emails = set()
    pos = 0
    target_len = len(target)
    
    while True:
        # Use str.find to locate the target pattern which is fast in C
        pos = text.find(target, pos)
        if pos == -1:
            break
        
        # Ensure the match is exact:
        # Check that the character right after the domain is not part of the email
        end_idx = pos + target_len
        if end_idx < len(text) and text[end_idx] in allowed_chars:
            pos += target_len  # skip if the domain continues (e.g. matching "example.com" in "example.com.au")
            continue

        # Walk backwards from the '@' sign to extract the email username
        start = pos - 1
        while start >= 0 and text[start] in allowed_chars:
            start -= 1
        
        username = text[start + 1: pos]
        if username:
            emails.add(username + target)
        
        pos += target_len  # Continue searching after this occurrence
    
    return emails