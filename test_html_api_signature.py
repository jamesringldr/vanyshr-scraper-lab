#!/usr/bin/env python3
"""
Test script to verify context.dev HTML API signature.

IMPORTANT: Before running, set your API key:
  export CONTEXT_DEV_API_KEY="your-key-here"

This script will help us understand the actual HTML method API
so we can fix all four HTML scrapers with the correct signature.
"""

import os
import sys
from context.dev import ContextDev

def test_html_api():
    """Test the context.dev HTML API and print its signature"""

    api_key = os.environ.get("CONTEXT_DEV_API_KEY")
    if not api_key:
        print("❌ CONTEXT_DEV_API_KEY not set")
        print("   Run: export CONTEXT_DEV_API_KEY='your-key'")
        return False

    try:
        client = ContextDev(api_key=api_key, timeout=30)
        print("✅ ContextDev client initialized")

        # Check available methods
        print("\n📋 Available methods on client.web:")
        web_methods = [m for m in dir(client.web) if not m.startswith('_')]
        for method in web_methods:
            print(f"   - {method}")

        # Try to find HTML-related methods
        html_methods = [m for m in web_methods if 'html' in m.lower() or 'scrape' in m.lower()]
        if html_methods:
            print(f"\n🎯 Found HTML-related methods: {html_methods}")

        # Test the most likely method
        test_url = "https://www.fastpeoplesearch.com/name/james-oehring_cameron-mo"
        print(f"\n🧪 Testing with URL: {test_url}")

        # Try most likely method names in order
        methods_to_try = [
            ('html', lambda: client.web.html(url=test_url, max_age_ms=86400000)),
            ('scrape', lambda: client.web.scrape(url=test_url, max_age_ms=86400000)),
            ('fetch', lambda: client.web.fetch(url=test_url, max_age_ms=86400000)),
            ('get', lambda: client.web.get(url=test_url, max_age_ms=86400000)),
        ]

        for method_name, method_func in methods_to_try:
            try:
                print(f"\n  Testing client.web.{method_name}()...")
                result = method_func()
                print(f"  ✅ SUCCESS! Method: client.web.{method_name}()")
                print(f"     Result type: {type(result)}")
                print(f"     Result attributes: {dir(result)}")

                # Check what the result contains
                if hasattr(result, 'html'):
                    print(f"     Has .html attribute: YES (length: {len(result.html)} chars)")
                elif hasattr(result, 'content'):
                    print(f"     Has .content attribute: YES (length: {len(result.content)} chars)")
                elif hasattr(result, 'text'):
                    print(f"     Has .text attribute: YES (length: {len(result.text)} chars)")
                elif hasattr(result, 'data'):
                    print(f"     Has .data attribute: YES (type: {type(result.data)})")
                else:
                    print(f"     Available attributes: {[a for a in dir(result) if not a.startswith('_')]}")

                print(f"\n🎉 CORRECT METHOD: Use client.web.{method_name}(url=..., max_age_ms=...)")
                print(f"   Result attribute for HTML: {[a for a in ['html', 'content', 'text', 'data'] if hasattr(result, a)][0]}")
                return True

            except AttributeError as e:
                print(f"  ❌ Method not found: {e}")
            except Exception as e:
                print(f"  ⚠️  Method exists but errored: {str(e)[:100]}")
                # If we got an error other than AttributeError, the method might exist
                if "url" in str(e).lower() or "invalid" in str(e).lower():
                    print(f"     (This might be a valid method with different params)")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    return False


if __name__ == "__main__":
    print("=" * 80)
    print("Context.dev HTML API Signature Test")
    print("=" * 80)
    success = test_html_api()
    sys.exit(0 if success else 1)
