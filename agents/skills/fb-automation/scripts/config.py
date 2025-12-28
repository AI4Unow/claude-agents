"""
Shared Configuration Constants for ProCaffe Scripts

Centralizes magic numbers and configuration values.
"""

import os
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
EXPORTS_DIR = PROJECT_DIR / "exports" / "tiktok"
DATA_DIR = PROJECT_DIR / "data"
LOGS_DIR = PROJECT_DIR / "logs"

# File size limits (bytes)
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # 100MB Publer limit
MIN_VIDEO_SIZE = 10000  # 10KB minimum valid video

# Timeouts (seconds)
UPLOAD_TIMEOUT = 300  # 5 min for large file uploads
JOB_POLL_TIMEOUT = 30  # Job status poll
PAGE_TIMEOUT = 30000  # Playwright page load (ms)
DEFAULT_TIMEOUT = 60  # General API calls

# Rate limiting
RATE_LIMIT_DELAY = 1.5  # seconds between API requests

# TikTok limits
TIKTOK_MAX_DURATION = 600  # 10 min max

# Timezone (Vietnam GMT+7)
LOCAL_TIMEZONE_OFFSET = 7  # Hours offset from UTC

# API endpoints
PUBLER_API_BASE = "https://app.publer.com/api/v1"

# Facebook URL pattern
FB_URL_PATTERN = r'https?://(www\.|m\.|web\.)?facebook\.com/.+'

# Playwright profile
PLAYWRIGHT_USER_DATA = "/tmp/playwright-fb-profile"

# Veo 3.1 Video Generation Configuration (Gemini API)
VEO_MODEL_ID = "veo-3.1-fast-generate-preview"  # Fast tier: $0.15/sec

# Veo cost tracking
VEO_COST_PER_SECOND = 0.15  # Veo 3.1 Fast tier
VEO_DAILY_BUDGET = 50.0     # USD
VEO_CLIP_DURATION = 8       # seconds per generation
VEO_POLL_INTERVAL = 10      # seconds between status checks
VEO_POLL_TIMEOUT = 300      # max wait for generation (5 min)

# AI-generated video directory
AI_GENERATED_DIR = EXPORTS_DIR / "ai-generated"

# TikTok Auto-Liker Configuration (CDP + Real Chrome Profile)
TIKTOK_CDP_PORT = 9222
TIKTOK_CHROME_PROFILE = Path(os.environ.get("HOME", "")) / "chrome-tiktok-profile"
TIKTOK_LIKE_DELAY_MIN = 30   # seconds between likes
TIKTOK_LIKE_DELAY_MAX = 90   # seconds between likes
TIKTOK_DAILY_LIKE_MAX = 50   # per-session limit (runs 6x/day = ~300 total)
TIKTOK_START_HOUR = 6        # 6 AM Vietnam time
TIKTOK_END_HOUR = 23         # 11 PM Vietnam time
TIKTOK_AUTO_LIKER_LOG_DIR = LOGS_DIR / "tiktok-auto-liker"

# TikTok Auto-Follower Configuration
TIKTOK_FOLLOW_DELAY_MIN = 30    # seconds between follows
TIKTOK_FOLLOW_DELAY_MAX = 120   # seconds between follows
TIKTOK_HOURLY_FOLLOW_MAX = 10   # conservative hourly limit
TIKTOK_FOLLOW_START_HOUR = 9    # 9 AM Vietnam time
TIKTOK_FOLLOW_END_HOUR = 23     # 11 PM Vietnam time
TIKTOK_AUTO_FOLLOWER_LOG_DIR = LOGS_DIR / "tiktok-auto-follower"
TIKTOK_FOLLOW_QUEUE_FILE = DATA_DIR / "follow-queue.json"
TIKTOK_FOLLOWED_FILE = DATA_DIR / "followed-accounts.json"

# TikTok Account Discovery - Keywords for business accounts
TIKTOK_SEARCH_KEYWORDS = [
    "khách sạn vietnam", "hotel vietnam",
    "quán cà phê", "coffee shop vietnam",
    "nhà hàng vietnam", "restaurant vietnam",
    "văn phòng", "office vietnam", "coworking vietnam"
]

# TikTok Competitors - accounts to scrape followers from
TIKTOK_COMPETITORS = [
    "cubesasia",
    "copen_coffee",
    "thegioimaypha"
]

# LinkedIn CDP Configuration
LINKEDIN_CDP_PORT = 9223
LINKEDIN_CHROME_PROFILE = Path(os.environ.get("HOME", "")) / "chrome-linkedin-profile"
LINKEDIN_CONNECT_DELAY_MIN = 120   # 2 min between connections
LINKEDIN_CONNECT_DELAY_MAX = 300   # 5 min between connections
LINKEDIN_ENGAGE_DELAY_MIN = 60     # 1 min between engagements
LINKEDIN_ENGAGE_DELAY_MAX = 180    # 3 min between engagements
LINKEDIN_DAILY_CONNECT_MAX = 25
LINKEDIN_DAILY_ENGAGE_MAX = 80
LINKEDIN_START_HOUR = 8            # 8 AM Vietnam time
LINKEDIN_END_HOUR = 11             # 11 AM Vietnam time
LINKEDIN_AUTO_LOG_DIR = LOGS_DIR / "linkedin-auto"
LINKEDIN_CONNECTIONS_FILE = DATA_DIR / "linkedin-connections.json"
LINKEDIN_ENGAGED_FILE = DATA_DIR / "linkedin-engaged.json"

# LinkedIn Target Job Titles (Vietnam)
LINKEDIN_TARGET_TITLES = [
    "Hotel Owner", "Hotel Manager", "General Manager Hotel",
    "Restaurant Owner", "F&B Manager", "Food and Beverage Director",
    "Cafe Owner", "Coffee Shop Owner", "Barista Manager",
    "Office Manager", "Facilities Manager", "Procurement Manager",
    "Purchasing Manager", "Operations Manager"
]

# LinkedIn Vietnam GeoUrn (for search filter)
LINKEDIN_VIETNAM_GEO_URN = "104195383"

# LinkedIn Sales Navigator Configuration
SALES_NAV_SEARCH_URL = "https://www.linkedin.com/sales/search/people"
SALES_NAV_LEAD_URL = "https://www.linkedin.com/sales/lead"
SALES_NAV_ACCOUNT_URL = "https://www.linkedin.com/sales/company"

# Sales Navigator Spotlight Filters
SPOTLIGHT_POSTED_30D = "recentlyPostedOnLinkedin"
SPOTLIGHT_CHANGED_JOB = "changedJobsInLastNinetyDays"
SPOTLIGHT_FOLLOWING = "followingYourCompany"
SPOTLIGHT_SHARED_CONNECTIONS = "commonConnections"

# Sales Navigator Boolean Queries (Vietnam Hospitality/F&B)
# Note: Keep queries simple - Sales Nav handles basic Boolean better than complex nested queries
SALES_NAV_QUERIES = [
    # Tier 1 - Strategic (Hotels & Resorts)
    {
        "name": "hotel_gm_vietnam",
        "query": '"General Manager" Hotel Vietnam',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 1,
        "tier": "tier1"
    },
    {
        "name": "resort_owner",
        "query": 'Resort Owner OR "Resort Manager" Vietnam',
        "spotlight": SPOTLIGHT_CHANGED_JOB,
        "priority": 1,
        "tier": "tier1"
    },
    {
        "name": "hotel_director",
        "query": '"Hotel Director" OR "Director of Operations" Hotel',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 1,
        "tier": "tier1"
    },
    # Tier 2 - Growth (F&B, Cafes, Restaurants)
    {
        "name": "coffee_shop_owner",
        "query": '"Coffee Shop" Owner Vietnam',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 2,
        "tier": "tier2"
    },
    {
        "name": "cafe_founder",
        "query": 'Cafe Founder OR "Quán cà phê" Owner',
        "spotlight": SPOTLIGHT_CHANGED_JOB,
        "priority": 2,
        "tier": "tier2"
    },
    {
        "name": "restaurant_owner_vietnam",
        "query": 'Restaurant Owner Vietnam OR "Nhà hàng"',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 2,
        "tier": "tier2"
    },
    {
        "name": "fnb_director",
        "query": '"F&B Director" OR "Food and Beverage Director"',
        "spotlight": SPOTLIGHT_CHANGED_JOB,
        "priority": 2,
        "tier": "tier2"
    },
    {
        "name": "fnb_manager_hotel",
        "query": '"F&B Manager" Hotel OR Resort',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 2,
        "tier": "tier2"
    },
    # Tier 3 - Scale (Offices, Procurement)
    {
        "name": "office_manager_vietnam",
        "query": '"Office Manager" Vietnam OR "Quản lý văn phòng"',
        "spotlight": SPOTLIGHT_CHANGED_JOB,
        "priority": 3,
        "tier": "tier3"
    },
    {
        "name": "procurement_hospitality",
        "query": '"Procurement Manager" Hospitality OR Hotel',
        "spotlight": SPOTLIGHT_CHANGED_JOB,
        "priority": 3,
        "tier": "tier3"
    },
    {
        "name": "purchasing_fnb",
        "query": '"Purchasing Manager" Restaurant OR Hotel Vietnam',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 3,
        "tier": "tier3"
    },
    {
        "name": "facilities_manager",
        "query": '"Facilities Manager" Vietnam Office OR Hotel',
        "spotlight": SPOTLIGHT_CHANGED_JOB,
        "priority": 3,
        "tier": "tier3"
    },
    # Additional high-value segments
    {
        "name": "coworking_owner",
        "query": 'Coworking Owner OR "Coworking Space" Manager Vietnam',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 2,
        "tier": "tier2"
    },
    {
        "name": "boutique_hotel",
        "query": '"Boutique Hotel" Owner OR Manager Vietnam',
        "spotlight": SPOTLIGHT_CHANGED_JOB,
        "priority": 1,
        "tier": "tier1"
    },
    {
        "name": "hospitality_consultant",
        "query": 'Hospitality Consultant Vietnam OR "F&B Consultant"',
        "spotlight": SPOTLIGHT_POSTED_30D,
        "priority": 2,
        "tier": "tier2"
    },
]

# Sales Navigator Rate Limits (conservative)
SALES_NAV_DAILY_SEARCH_MAX = 100      # max search result views/day
SALES_NAV_DAILY_PROFILE_VIEW_MAX = 50  # max profile views/day
SALES_NAV_DAILY_INMAIL_MAX = 5         # preserve InMail credits
SALES_NAV_WEEKLY_INMAIL_MAX = 15       # weekly InMail cap

# Sales Navigator Connection Note Templates (300 char max)
SALES_NAV_CONNECT_TEMPLATES = {
    "value_first": """Chào anh/chị {name}!

Thấy anh/chị có kinh nghiệm trong {industry}. ProCaffe đang hỗ trợ nhiều {segment} tại Vietnam với thiết bị cà phê chuyên nghiệp.

Rất mong được kết nối để chia sẻ thêm!""",

    "common_ground": """Chào anh/chị {name}!

Rất ấn tượng với bài viết gần đây về {topic}. Tôi cũng đang trong ngành F&B/Hospitality.

Kết nối để trao đổi thêm nhé!""",

    "direct": """Chào anh/chị {name}!

ProCaffe là đối tác thiết bị cà phê cho Marriott, Accor... tại VN. Đang tìm hiểu thêm về nhu cầu của {company}.

Có thể kết nối và trao đổi nhanh được không ạ?"""
}

# Sales Navigator InMail Template
SALES_NAV_INMAIL_TEMPLATE = {
    "subject": "Câu hỏi về {company}",
    "body": """Chào anh/chị {name},

Tôi đang nghiên cứu về thị trường F&B/Hospitality tại {city}. Thấy {company} đang phát triển, tôi tò mò về cách tiếp cận thiết bị cà phê cho khách hàng.

ProCaffe hiện đang hỗ trợ Marriott, Accor, IHG với máy pha cà phê chuyên nghiệp.

Anh/chị có 15 phút tuần này để trao đổi nhanh không ạ?

Best,
ProCaffe Vietnam"""
}

# Lead Tracker Files
LINKEDIN_LEADS_FILE = DATA_DIR / "linkedin-leads.json"
LINKEDIN_INMAIL_QUEUE_FILE = DATA_DIR / "linkedin-inmail-queue.json"
LINKEDIN_INMAIL_SENT_FILE = DATA_DIR / "linkedin-inmail-sent.json"
LINKEDIN_WEEKLY_REPORTS_DIR = PROJECT_DIR / "reports" / "linkedin-weekly"

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT = PROJECT_DIR / "firebase_service_account.json"
FIREBASE_PROJECT_ID = "procaffe-d3230"
FIREBASE_STORAGE_BUCKET = "procaffe-d3230.firebasestorage.app"

# CRM Configuration - Social Media Lead Management
CRM_LEADS_COLLECTION = "leads"
CRM_LEADS_EXPORT_DIR = PROJECT_DIR / "exports" / "crm"
CRM_LEADS_EXPORT_FILE = CRM_LEADS_EXPORT_DIR / "leads-export.csv"

# Lead status values
LEAD_STATUS_COLD = "cold"
LEAD_STATUS_ENGAGED = "engaged"
LEAD_STATUS_CONTACTED = "contacted"
LEAD_STATUS_QUALIFIED = "qualified"
LEAD_STATUS_DISQUALIFIED = "disqualified"

# Lead tiers
LEAD_TIER_1 = "tier1"  # High-value (score >= 30)
LEAD_TIER_2 = "tier2"  # Medium (score 10-29)
LEAD_TIER_3 = "tier3"  # Low (score < 10)

# Engagement scoring weights
ENGAGEMENT_WEIGHTS = {
    "follower": 5,       # They follow us
    "following": 2,      # We follow them
    "liker": 3,          # Liked our content
    "commenter": 8,      # Commented on our content
    "connection": 5,     # LinkedIn connection
    "profile_viewer": 4, # Viewed our profile
    "message_reply": 15, # Replied to message
}

# Facebook Content Import Configuration
FB_PAGE_URL = "https://www.facebook.com/ProCaffeGroup"
FB_CDP_PORT = 9224  # Separate from TikTok (9222) and LinkedIn (9223)
FB_CHROME_PROFILE = Path(os.environ.get("HOME", "")) / "chrome-fb-profile"
FB_EXPORTS_DIR = PROJECT_DIR / "exports" / "fb"
FB_VIDEOS_DIR = FB_EXPORTS_DIR / "videos"
FB_IMAGES_DIR = FB_EXPORTS_DIR / "images"
FB_POSTS_FILE = DATA_DIR / "fb-posts.json"
FB_SCRAPE_PROGRESS_FILE = DATA_DIR / "fb-scrape-progress.json"
FB_IMPORT_PROGRESS_FILE = DATA_DIR / "fb-import-progress.json"
FB_APIFY_RAW_FILE = DATA_DIR / "apify-fb-raw.json"
FB_VIDEO_IDS_FILE = DATA_DIR / "fb-video-ids.json"

# Pinecone Configuration (Second Brain)
PINECONE_API_KEY = "pcsk_4mNEmD_QUWDdZ57zcLegpsU5j7Jpss5mj3GNHybWtWDQTLn5bBYQJqaJvgPjpsefhrQvzD"
PINECONE_INDEX_NAME = "procaffe-kb"
PINECONE_DIMENSION = 768  # Gemini text-embedding-004
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"

# Cohere Configuration (Reranking)
COHERE_API_KEY = "tA6Fj3jXGYa5csSZhrmWk6HpTcxJsbfodGH3rl7Q"
COHERE_RERANK_MODEL = "rerank-v4.0-pro"  # Latest model (Dec 2025)
