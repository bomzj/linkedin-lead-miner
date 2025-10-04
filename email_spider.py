from collections import defaultdict
import re
import scrapy
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urlparse, urlunparse


class EmailSpider(scrapy.Spider):
    name = 'email_spider'

    def __init__(self, start_urls, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Split the comma-separated start URLs into a list
        if isinstance(start_urls, str):
            start_urls = start_urls.split(',')

        self.start_urls = ensure_urls_valid(start_urls)

        # Use default values that will be overridden by from_crawler()
        self.max_pages_per_domain = 50
        self.priority_url_keywords = []

        # Set to store already found emails
        self.found_emails = []

         # Counter to track pages crawled per domain
        self.pages_crawled_per_domain = defaultdict(int)


    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                # keep original domain for matching scrapped emails with source domain later
                # in case of redirect to new domain, or some sites can have different email domains
                meta={'origin_domain': domain(url)}
            )


    def parse(self, response):
        origin_domain = response.meta['origin_domain']
        current_domain = domain(response.url)

        # Use the efficient email extraction function, 
        # NOTE: regex is very slow against whole response
        emails = extract_emails(response.text, current_domain)
        
        for email in emails:
            scrapped_item = {
                'email': email,
                'origin_domain': origin_domain
            }
            # TODO: use item pipeline instead of accumulated found_emails property
            #  https://docs.scrapy.org/en/latest/topics/item-pipeline.html#topics-item-pipeline
            self.found_emails.append(scrapped_item)
            yield scrapped_item

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
                    priority=len(prioritized_links) - index,  # higher for earlier links
                    meta={'origin_domain': origin_domain}  # propagate
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
    """Sort links so that whole-word keyword matches rank higher than partial matches."""
    def priority_score(link):
        path = urlparse(link.url).path.lower()

        for index, keyword in enumerate(priority_keywords):
            kw = re.escape(keyword.lower())

            # Check whole word match first (higher priority)
            if re.search(rf'\b{kw}\b', path):
                return index  # exact match - highest priority

        # If no exact matches, check for partial matches but add penalty
        for index, keyword in enumerate(priority_keywords):
            if keyword.lower() in path:
                return index + len(priority_keywords)  # penalty pushes lower

        # If no matches at all
        return float('inf')

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