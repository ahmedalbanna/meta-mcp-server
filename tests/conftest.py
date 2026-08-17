"""Shared pytest fixtures: a mocked Meta SDK that blocks all network I/O.

The mock_meta_sdk fixture replaces the facebook-business SDK classes and the
raw-call helpers with stdlib MagicMocks, so every tool can be exercised offline.
"""

import pytest
from unittest import mock

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


@pytest.fixture
def mock_meta_sdk():
    def fake_to_dict(obj):
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

    with mock.patch.multiple(
        "facebook_business.api.FacebookAdsApi",
        init=mock.DEFAULT,
        get_default_api=mock.DEFAULT,
    ) as api_mocks:
        with mock.patch(
            "src.helpers.api_call", return_value={"data": [], "paging": {}}
        ):
            with mock.patch("src.helpers.page_api_call", return_value={"data": []}):
                with mock.patch("src.helpers.to_dict", new=fake_to_dict):
                    with mock.patch("src.automation.to_dict", new=fake_to_dict):
                        with mock.patch("src.finance.to_dict", new=fake_to_dict):
                            with mock.patch("src.pages.to_dict", new=fake_to_dict):
                                with mock.patch(
                                    "src.resources_prompts.to_dict", new=fake_to_dict
                                ):
                                    with mock.patch(
                                        "src.business.to_dict", new=fake_to_dict
                                    ):
                                        with mock.patch(
                                            "src.helpers.get_page_api"
                                        ) as page_api:
                                            with mock.patch(
                                                "src.instagram.requests"
                                            ) as requests_mock:
                                                for path in SDK_CLASSES:
                                                    mock.patch(path).start()
                                                try:
                                                    yield api_mocks
                                                finally:
                                                    mock.patch.stopall()


@pytest.fixture
def mock_meta_sdk_recorded():
    """Like mock_meta_sdk but api_call/page_api_call record their calls.

    Patches the helper references at the module level (where each tool module
    imported them via `from src.helpers import ...`), so the recorded calls
    reflect the real request params/URLs the tools build.
    """

    def fake_to_dict(obj):
        if isinstance(obj, dict):
            return obj
        try:
            data = obj.export_all_data()
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"id": "123", "mocked": True}

    api_call = mock.MagicMock(return_value={"data": [], "paging": {}})
    page_api_call = mock.MagicMock(return_value={"data": []})
    with mock.patch.multiple(
        "facebook_business.api.FacebookAdsApi",
        init=mock.DEFAULT,
        get_default_api=mock.DEFAULT,
    ):
        with mock.patch("src.helpers.api_call", new=api_call):
            with mock.patch("src.helpers.page_api_call", new=page_api_call):
                with mock.patch("src.whatsapp.api_call", new=api_call):
                    with mock.patch("src.finance.api_call", new=api_call):
                        with mock.patch("src.instagram.api_call", new=api_call):
                            with mock.patch("src.discovery.api_call", new=api_call):
                                with mock.patch(
                                    "src.messenger.page_api_call",
                                    new=page_api_call,
                                ):
                                    with mock.patch(
                                        "src.pages.page_api_call",
                                        new=page_api_call,
                                    ):
                                        with mock.patch(
                                            "src.helpers.to_dict",
                                            new=fake_to_dict,
                                        ):
                                            with mock.patch(
                                                "src.automation.to_dict",
                                                new=fake_to_dict,
                                            ):
                                                with mock.patch(
                                                    "src.finance.to_dict",
                                                    new=fake_to_dict,
                                                ):
                                                    with mock.patch(
                                                        "src.pages.to_dict",
                                                        new=fake_to_dict,
                                                    ):
                                                        with mock.patch(
                                                            "src.resources_prompts.to_dict",
                                                            new=fake_to_dict,
                                                        ):
                                                            with mock.patch(
                                                                "src.business.to_dict",
                                                                new=fake_to_dict,
                                                            ):
                                                                with mock.patch(
                                                                    "src.helpers.get_page_api"
                                                                ):
                                                                    with mock.patch(
                                                                        "src.instagram.requests"
                                                                    ):
                                                                        for path in (
                                                                            SDK_CLASSES
                                                                        ):
                                                                            mock.patch(
                                                                                path
                                                                            ).start()
                                                                        try:
                                                                            yield {
                                                                                "api_call": api_call,
                                                                                "page_api_call": page_api_call,
                                                                            }
                                                                        finally:
                                                                            mock.patch.stopall()


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
    "resources_prompts",
)

# Modules that expose @mcp.tool() tools (resources_prompts only has resources/prompts)
TOOL_MODULES = tuple(m for m in ALL_MODULES if m != "resources_prompts")


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
        finance,
        insights,
        instagram,
        leads,
        messenger,
        pages,
        reports,
        resources_prompts,
        whatsapp,
    )

    for name in ALL_MODULES:
        module = {
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
            "finance": finance,
            "insights": insights,
            "instagram": instagram,
            "leads": leads,
            "messenger": messenger,
            "pages": pages,
            "reports": reports,
            "resources_prompts": resources_prompts,
            "whatsapp": whatsapp,
        }[name]
        module.register(recorder)
    return recorder
