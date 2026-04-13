"""
APIclaw — Amazon product intelligence tools.
Base URL : https://apiclaw.io
Auth     : Authorization: Bearer hms_live_xxx
Spec     : openapi-spec-latest.json (v2)

8 tools exposed to the LLM:
  1. search_amazon_products    — keyword/category/filter search
  2. get_amazon_competitors     — competitors by ASIN
  3. get_product_history        — price/BSR/sales time-series
  4. search_markets             — market-level aggregated data
  5. get_categories             — Amazon category hierarchy
  6. get_realtime_product       — live product page scrape
  7. analyze_reviews            — sentiment + consumer insights
  8. detect_prompt_injection    — safety check on text input
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from backend.config import get_settings

log = logging.getLogger(__name__)

BASE_URL = "https://api.apiclaw.io"


# ---------------------------------------------------------------------------
# HTTP client helper
# ---------------------------------------------------------------------------

def _post(path: str, body: dict) -> dict:
    settings = get_settings()
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {settings.apiclaw_api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Product search
# ---------------------------------------------------------------------------

def search_amazon_products(
    keyword: str,
    category_path: list[str] | None = None,
    monthly_sales_min: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    bsr_max: int | None = None,
    page_size: int = 10,
    sort_by: str = "monthlySalesFloor",
    sort_order: str = "desc",
    marketplace: str = "US",
) -> str:
    """Search Amazon products by keyword and optional filters. Returns JSON string."""
    body: dict[str, Any] = {
        "keyword": keyword,
        "marketplace": marketplace,
        "pageSize": min(page_size, 20),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    if category_path:    body["categoryPath"] = category_path
    if monthly_sales_min is not None: body["monthlySalesMin"] = monthly_sales_min
    if price_min is not None:         body["priceMin"] = price_min
    if price_max is not None:         body["priceMax"] = price_max
    if bsr_max is not None:           body["bsrMax"] = bsr_max

    try:
        data = _post("/openapi/v2/products/search", body)
        products = data.get("data", []) or []
        slim = [{
            "asin": p.get("asin"), "title": p.get("title"),
            "price": p.get("price"), "bsr": p.get("bsr"),
            "monthlySales": p.get("monthlySalesFloor"),
            "monthlyRevenue": p.get("monthlyRevenueFloor"),
            "rating": p.get("rating"), "ratingCount": p.get("ratingCount"),
            "brandName": p.get("brandName"), "fulfillment": p.get("fulfillment"),
            "categoryPath": p.get("categoryPath"),
        } for p in products[:10]]
        return json.dumps({"success": True, "count": len(slim), "products": slim})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# 2. Competitor lookup
# ---------------------------------------------------------------------------

def get_amazon_competitors(
    asin: str,
    page_size: int = 10,
    marketplace: str = "US",
) -> str:
    """Find competitor products for a given Amazon ASIN. Returns JSON string."""
    body = {"asin": asin, "pageSize": min(page_size, 20),
            "sortBy": "monthlySalesFloor", "sortOrder": "desc",
            "marketplace": marketplace}
    try:
        data = _post("/openapi/v2/products/competitors", body)
        products = data.get("data", []) or []
        slim = [{"asin": p.get("asin"), "title": p.get("title"),
                 "price": p.get("price"), "monthlySales": p.get("monthlySalesFloor"),
                 "rating": p.get("rating"), "brandName": p.get("brandName")}
                for p in products[:10]]
        return json.dumps({"success": True, "count": len(slim), "competitors": slim})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# 3. Product history
# ---------------------------------------------------------------------------

def get_product_history(
    asin: str,
    start_date: str,
    end_date: str,
    marketplace: str = "US",
) -> str:
    """
    Get price/BSR/sales history for an ASIN over a date range.
    Dates: YYYY-MM-DD. Max range: 730 days.
    Returns JSON string.
    """
    body = {"asin": asin, "startDate": start_date,
            "endDate": end_date, "marketplace": marketplace}
    try:
        data = _post("/openapi/v2/products/history", body)
        ts = data.get("data", {}) or {}
        return json.dumps({"success": True, "asin": asin, "history": {
            "timestamps":       ts.get("timestamps", [])[-30:],
            "price":            ts.get("price", [])[-30:],
            "bsr":              ts.get("bsr", [])[-30:],
            "monthlySalesFloor": ts.get("monthlySalesFloor", [])[-30:],
            "rating":           ts.get("rating", [])[-30:],
        }})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# 4. Market search
# ---------------------------------------------------------------------------

def search_markets(
    category_keyword: str,
    sample_avg_monthly_sales_min: float | None = None,
    page_size: int = 10,
    marketplace: str = "US",
) -> str:
    """Search Amazon market/category data. Returns JSON string."""
    body: dict[str, Any] = {
        "categoryKeyword": category_keyword,
        "marketplace": marketplace,
        "pageSize": min(page_size, 20),
        "sortBy": "sampleAvgMonthlySales",
        "sortOrder": "desc",
    }
    if sample_avg_monthly_sales_min is not None:
        body["sampleAvgMonthlySalesMin"] = sample_avg_monthly_sales_min
    try:
        data = _post("/openapi/v2/markets/search", body)
        markets = data.get("data", []) or []
        slim = [{"categoryPath": m.get("categoryPath"),
                 "totalSkuCount": m.get("totalSkuCount"),
                 "avgMonthlySales": m.get("sampleAvgMonthlySales"),
                 "avgMonthlyRevenue": m.get("sampleAvgMonthlyRevenue"),
                 "avgPrice": m.get("sampleAvgPrice"),
                 "avgRating": m.get("sampleAvgRating"),
                 "fbaRate": m.get("sampleFbaRate")}
                for m in markets[:10]]
        return json.dumps({"success": True, "count": len(slim), "markets": slim})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# 5. Categories
# ---------------------------------------------------------------------------

def get_categories(
    parent_category_path: list[str] | None = None,
    category_keyword: str | None = None,
    marketplace: str = "US",
) -> str:
    """Browse Amazon category hierarchy. Returns JSON string."""
    body: dict[str, Any] = {"marketplace": marketplace}
    if parent_category_path: body["parentCategoryPath"] = parent_category_path
    if category_keyword:      body["categoryKeyword"] = category_keyword
    try:
        data = _post("/openapi/v2/categories", body)
        cats = data.get("data", []) or []
        slim = [{"categoryId": c.get("categoryId"), "categoryName": c.get("categoryName"),
                 "categoryPath": c.get("categoryPath"), "hasChildren": c.get("hasChildren"),
                 "level": c.get("level")} for c in cats[:20]]
        return json.dumps({"success": True, "count": len(slim), "categories": slim})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# 6. Realtime product
# ---------------------------------------------------------------------------

def get_realtime_product(asin: str, marketplace: str = "US") -> str:
    """Scrape live Amazon product data for an ASIN. Returns JSON string."""
    body = {"asin": asin, "marketplace": marketplace}
    try:
        data = _post("/openapi/v2/realtime/product", body)
        p = data.get("data", {}) or {}
        return json.dumps({"success": True, "product": {
            "asin": p.get("asin"), "title": p.get("title"),
            "brandName": p.get("brandName"), "rating": p.get("rating"),
            "ratingCount": p.get("ratingCount"), "imageUrl": p.get("imageUrl"),
            "categoryPath": p.get("categoryPath"), "features": p.get("features", [])[:5],
            "description": (p.get("description") or "")[:500],
            "specifications": p.get("specifications"),
            "bestsellersRank": p.get("bestsellersRank"),
            "dimensions": p.get("dimensions"),
            "link": p.get("link"),
        }})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# 7. Reviews analysis
# ---------------------------------------------------------------------------

def analyze_reviews(
    asins: list[str] | None = None,
    category_path: list[str] | None = None,
    period: str = "6m",
    marketplace: str = "US",
) -> str:
    """
    Analyze Amazon reviews for ASINs or a category.
    Returns sentiment, rating distribution, and consumer insights as JSON.
    """
    if asins:
        body = {"mode": "asin", "asins": asins[:10], "period": period, "marketplace": marketplace}
    elif category_path:
        body = {"mode": "category", "categoryPath": category_path, "period": period, "marketplace": marketplace}
    else:
        return json.dumps({"success": False, "error": "Provide asins or category_path."})
    try:
        data = _post("/openapi/v2/reviews/analysis", body)
        r = data.get("data", {}) or {}
        return json.dumps({"success": True, "analysis": {
            "avgRating": r.get("avgRating"),
            "reviewCount": r.get("reviewCount"),
            "verifiedRate": r.get("verifiedRate"),
            "ratingDistribution": r.get("ratingDistribution"),
            "sentimentDistribution": r.get("sentimentDistribution"),
            "topKeywords": r.get("topKeywords", [])[:10],
            "consumerInsights": r.get("consumerInsights", [])[:5],
        }})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# 8. Prompt injection detection
# ---------------------------------------------------------------------------

def detect_prompt_injection(text: str) -> str:
    """
    Detect prompt injection attacks in user input text.
    Uses APIclaw's fine-tuned DeBERTa model.
    Returns {label, score, isInjection} as JSON.
    """
    body = {"text": text[:2000]}
    try:
        data = _post("/openapi/v2/model/prompt-injection-detect", body)
        r = data.get("data", {}) or {}
        return json.dumps({"success": True, "result": {
            "label": r.get("label"),
            "score": r.get("score"),
            "isInjection": r.get("isInjection"),
        }})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# Tool dispatcher — called by providers when the LLM requests a tool
# ---------------------------------------------------------------------------

APICLAW_TOOL_MAP = {
    "search_amazon_products":  search_amazon_products,
    "get_amazon_competitors":  get_amazon_competitors,
    "get_product_history":     get_product_history,
    "search_markets":          search_markets,
    "get_categories":          get_categories,
    "get_realtime_product":    get_realtime_product,
    "analyze_reviews":         analyze_reviews,
    "detect_prompt_injection": detect_prompt_injection,
}


def call_apiclaw_tool(name: str, args: dict) -> str:
    fn = APICLAW_TOOL_MAP.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown APIclaw tool: {name}"})
    try:
        return fn(**args)
    except TypeError as exc:
        return json.dumps({"error": f"Bad args for {name}: {exc}"})


# ---------------------------------------------------------------------------
# Tool definitions for each LLM provider format
# ---------------------------------------------------------------------------

# ── OpenAI ──────────────────────────────────────────────────────────────────
OPENAI_APICLAW_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_amazon_products",
            "description": "Search Amazon products by keyword with optional category and metric filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword":          {"type": "string",  "description": "Search keyword e.g. 'yoga mat'"},
                    "category_path":    {"type": "array", "items": {"type": "string"}, "description": "Category hierarchy e.g. ['Sports & Outdoors']"},
                    "monthly_sales_min":{"type": "integer", "description": "Minimum monthly sales"},
                    "price_min":        {"type": "number",  "description": "Minimum price"},
                    "price_max":        {"type": "number",  "description": "Maximum price"},
                    "bsr_max":          {"type": "integer", "description": "Maximum Best Sellers Rank"},
                    "page_size":        {"type": "integer", "description": "Number of results (max 20)"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_amazon_competitors",
            "description": "Find competitor products for a given Amazon ASIN.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asin":      {"type": "string", "description": "Amazon ASIN e.g. B07FR2V8SH"},
                    "page_size": {"type": "integer"},
                },
                "required": ["asin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_history",
            "description": "Get price, BSR, and sales history for an Amazon ASIN over a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asin":       {"type": "string", "description": "Amazon ASIN"},
                    "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                    "end_date":   {"type": "string", "description": "End date YYYY-MM-DD"},
                },
                "required": ["asin", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_markets",
            "description": "Search Amazon market/category data with demand and competition metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_keyword": {"type": "string", "description": "Category keyword e.g. 'fitness'"},
                    "sample_avg_monthly_sales_min": {"type": "number"},
                },
                "required": ["category_keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_realtime_product",
            "description": "Get live Amazon product details by scraping the product page now.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asin": {"type": "string", "description": "Amazon ASIN"},
                },
                "required": ["asin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_reviews",
            "description": "Analyze Amazon reviews for sentiment, ratings, and consumer insights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asins":         {"type": "array", "items": {"type": "string"}, "description": "List of ASINs"},
                    "category_path": {"type": "array", "items": {"type": "string"}},
                    "period":        {"type": "string", "description": "e.g. 6m, 12m, 3m"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_prompt_injection",
            "description": "Check if a text string contains a prompt injection attack.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to analyze"},
                },
                "required": ["text"],
            },
        },
    },
]


# ── Gemini ───────────────────────────────────────────────────────────────────
def _gemini_apiclaw_tools():
    from google.genai import types

    def _obj(props: dict, required: list[str] | None = None) -> types.Schema:
        schema_props = {k: types.Schema(type=types.Type.STRING if v == "string"
                                        else types.Type.INTEGER if v == "integer"
                                        else types.Type.NUMBER if v == "number"
                                        else types.Type.BOOLEAN if v == "boolean"
                                        else types.Type.ARRAY,
                                        description="")
                        for k, v in props.items()}
        return types.Schema(
            type=types.Type.OBJECT,
            properties=schema_props,
            required=required or [],
        )

    return types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="search_amazon_products",
            description="Search Amazon products by keyword with optional filters.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "keyword":          types.Schema(type=types.Type.STRING),
                    "monthly_sales_min":types.Schema(type=types.Type.INTEGER),
                    "price_max":        types.Schema(type=types.Type.NUMBER),
                    "bsr_max":          types.Schema(type=types.Type.INTEGER),
                    "page_size":        types.Schema(type=types.Type.INTEGER),
                },
                required=["keyword"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_amazon_competitors",
            description="Find competitor products for a given Amazon ASIN.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"asin": types.Schema(type=types.Type.STRING)},
                required=["asin"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_product_history",
            description="Get price/BSR/sales history for an ASIN over a date range.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "asin":       types.Schema(type=types.Type.STRING),
                    "start_date": types.Schema(type=types.Type.STRING),
                    "end_date":   types.Schema(type=types.Type.STRING),
                },
                required=["asin", "start_date", "end_date"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_markets",
            description="Search Amazon market/category aggregated data.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"category_keyword": types.Schema(type=types.Type.STRING)},
                required=["category_keyword"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_realtime_product",
            description="Get live Amazon product details by scraping the product page.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"asin": types.Schema(type=types.Type.STRING)},
                required=["asin"],
            ),
        ),
        types.FunctionDeclaration(
            name="analyze_reviews",
            description="Analyze Amazon reviews for sentiment and consumer insights.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "period": types.Schema(type=types.Type.STRING),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="detect_prompt_injection",
            description="Detect prompt injection attacks in text.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"text": types.Schema(type=types.Type.STRING)},
                required=["text"],
            ),
        ),
    ])


# ── Anthropic ────────────────────────────────────────────────────────────────
ANTHROPIC_APICLAW_TOOLS: list[dict] = [
    {
        "name": "search_amazon_products",
        "description": "Search Amazon products by keyword with optional filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword":          {"type": "string"},
                "monthly_sales_min":{"type": "integer"},
                "price_max":        {"type": "number"},
                "bsr_max":          {"type": "integer"},
                "page_size":        {"type": "integer"},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_amazon_competitors",
        "description": "Find competitor products for a given Amazon ASIN.",
        "input_schema": {
            "type": "object",
            "properties": {"asin": {"type": "string"}},
            "required": ["asin"],
        },
    },
    {
        "name": "get_product_history",
        "description": "Get price/BSR/sales history for an ASIN over a date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asin":       {"type": "string"},
                "start_date": {"type": "string"},
                "end_date":   {"type": "string"},
            },
            "required": ["asin", "start_date", "end_date"],
        },
    },
    {
        "name": "get_realtime_product",
        "description": "Get live Amazon product details by scraping the product page.",
        "input_schema": {
            "type": "object",
            "properties": {"asin": {"type": "string"}},
            "required": ["asin"],
        },
    },
    {
        "name": "analyze_reviews",
        "description": "Analyze Amazon reviews for sentiment and consumer insights.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asins":  {"type": "array", "items": {"type": "string"}},
                "period": {"type": "string"},
            },
        },
    },
    {
        "name": "detect_prompt_injection",
        "description": "Detect prompt injection attacks in text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]
