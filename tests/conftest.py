"""Shared pytest fixtures: a mocked Meta SDK that blocks all network I/O.

The mock_meta_sdk fixture replaces the facebook-business SDK classes and the
raw-call helpers with stdlib MagicMocks, so every tool can be exercised offline.
"""

from contextlib import ExitStack
from unittest import mock

import pytest

# Classes that tools instantiate inside register() — replaced with MagicMock.
SDK_CLASSES = [
    "facebook_business.adobjects.adaccount.AdAccount",
    "facebook_business.adobjects.campaign.Campaign",
    "facebook_business.adobjects.adset.AdSet",
    "facebook_business.adobjects.ad.Ad",
    "facebook_business.adobjects.adcreative.AdCreative",
    "facebook_business.adobjects.adimage.AdImage",
    "facebook_business.adobjects.advideo.AdVideo",
    "facebook_business.adobjects.page.Page",
    "facebook_business.adobjects.customaudience.CustomAudience",
    "facebook_business.adobjects.business.Business",
    "facebook_business.adobjects.productcatalog.ProductCatalog",
    "facebook_business.adobjects.productset.ProductSet",
    "facebook_business.adobjects.productitem.ProductItem",
    "facebook_business.adobjects.productfeed.ProductFeed",
    "facebook_business.adobjects.commercemerchantsettings.CommerceMerchantSettings",
    "facebook_business.adobjects.commerceorder.CommerceOrder",
    "facebook_business.adobjects.leadgenform.LeadgenForm",
    "facebook_business.adobjects.lead.Lead",
    "facebook_business.adobjects.businessuser.BusinessUser",
    "facebook_business.adobjects.event.Event",
]


def _fake_to_dict(obj):
    """Convert mocked SDK objects to a plain dict for JSON serialisation."""
    if isinstance(obj, dict):
        return obj
    try:
        data = obj.export_all_data()
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"id": "123", "mocked": True}


# Paths that need to_dict patched (each module imports to_dict independently).
_TO_DICT_PATHS = [
    "src.helpers",
    "src.automation",
    "src.finance",
    "src.pages",
    "src.business",
    "src.campaigns",
    "src.adsets",
    "src.ads",
    "src.insights",
    "src.breakdowns",
    "src.reports",
    "src.audiences",
    "src.instagram",
    "src.catalog",
    "src.leads",
    "src.messenger",
    "src.whatsapp",
    "src.creatives",
    "src.discovery",
    "src.events",
    "src.webhook_automations",
    "src.scheduler",
    "src.metrics",
]


@pytest.fixture
def mock_meta_sdk():
    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.multiple(
                "facebook_business.api.FacebookAdsApi",
                init=mock.DEFAULT,
                get_default_api=mock.DEFAULT,
            )
        )
        stack.enter_context(
            mock.patch("src.helpers.api_call", return_value={"data": [], "paging": {}})
        )
        stack.enter_context(
            mock.patch("src.helpers.page_api_call", return_value={"data": []})
        )
        for mod_path in _TO_DICT_PATHS:
            stack.enter_context(mock.patch(f"{mod_path}.to_dict", new=_fake_to_dict, create=True))
        stack.enter_context(mock.patch("src.helpers.get_page_api"))
        stack.enter_context(mock.patch("src.instagram.requests"))
        for path in SDK_CLASSES:
            stack.enter_context(mock.patch(path))
        yield


@pytest.fixture
def mock_meta_sdk_recorded():
    """Like mock_meta_sdk but api_call/page_api_call record their calls.

    Patches the helper references at the module level (where each tool module
    imported them via `from src.helpers import ...`), so the recorded calls
    reflect the real request params/URLs the tools build.
    """
    api_call = mock.MagicMock(return_value={"data": [], "paging": {}})
    page_api_call = mock.MagicMock(return_value={"data": []})

    # Modules that import api_call and/or page_api_call at module level.
    api_call_patches = [
        "src.helpers.api_call",
        "src.whatsapp.api_call",
        "src.instagram.api_call",
        "src.discovery.api_call",
    ]
    page_api_call_patches = [
        "src.helpers.page_api_call",
        "src.messenger.page_api_call",
        "src.pages.page_api_call",
    ]

    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.multiple(
                "facebook_business.api.FacebookAdsApi",
                init=mock.DEFAULT,
                get_default_api=mock.DEFAULT,
            )
        )
        for p in api_call_patches:
            stack.enter_context(mock.patch(p, new=api_call))
        for p in page_api_call_patches:
            stack.enter_context(mock.patch(p, new=page_api_call))
        for mod_path in _TO_DICT_PATHS:
            stack.enter_context(mock.patch(f"{mod_path}.to_dict", new=_fake_to_dict, create=True))
        stack.enter_context(mock.patch("src.helpers.get_page_api"))
        stack.enter_context(mock.patch("src.instagram.requests"))
        for path in SDK_CLASSES:
            stack.enter_context(mock.patch(path))
        yield {"api_call": api_call, "page_api_call": page_api_call}


class Recorder:
    """Minimal stand-in for FastMCP that records registered tools/resources/prompts."""

    def __init__(self):
        self.tools = {}
        self.resources = []
        self.prompts = []

    def tool(self, *args, **kwargs):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator

    def resource(self, *args, **kwargs):
        def decorator(fn):
            self.resources.append(fn.__name__)
            return fn

        return decorator

    def prompt(self, *args, **kwargs):
        def decorator(fn):
            self.prompts.append(fn.__name__)
            return fn

        return decorator


ALL_MODULES = (
    "discovery",
    "campaigns",
    "adsets",
    "ads",
    "insights",
    "breakdowns",
    "reports",
    "audiences",
    "pages",
    "instagram",
    "leads",
    "messenger",
    "whatsapp",
    "automation",
    "finance",
    "catalog",
    "business",
    "creatives",
    "events",
    "webhook_automations",
    "scheduler",
    "metrics",
)

# All modules now expose tools (and per-module resources/prompts)
TOOL_MODULES = ALL_MODULES


def register_all(recorder):
    """Register every module onto the recorder and return the tool dict."""
    from src import (
        ads,
        adsets,
        audiences,
        automation,
        breakdowns,
        business,
        campaigns,
        catalog,
        creatives,
        discovery,
        events,
        finance,
        insights,
        instagram,
        leads,
        messenger,
        metrics,
        pages,
        reports,
        scheduler,
        webhook_automations,
        whatsapp,
    )

    module_map = {
        "ads": ads,
        "adsets": adsets,
        "audiences": audiences,
        "automation": automation,
        "breakdowns": breakdowns,
        "business": business,
        "campaigns": campaigns,
        "catalog": catalog,
        "creatives": creatives,
        "discovery": discovery,
        "events": events,
        "finance": finance,
        "insights": insights,
        "instagram": instagram,
        "leads": leads,
        "messenger": messenger,
        "metrics": metrics,
        "pages": pages,
        "reports": reports,
        "scheduler": scheduler,
        "webhook_automations": webhook_automations,
        "whatsapp": whatsapp,
    }
    for name in ALL_MODULES:
        module_map[name].register(recorder)
    return recorder
