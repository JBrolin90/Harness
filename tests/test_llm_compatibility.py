"""Integration tests for LLM provider compatibility.

Run with: python3 test_llm_compatibility.py [--provider <name>]

This tests actual LLM providers to ensure they respond correctly to tool-calling prompts.
"""
import sys
import os
import argparse
import json
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from llm.provider import ProviderManager, ProviderConfig
from llm.brain import consult_llm as call_llm
from systemprompt import build_system_prompt
from tools import TOOLS


# Prompt that typically requires tool use or demonstrates reasoning
TEST_PROMPTS = [
    "Please read and understand brain.py. What does it do?",
    "List the files in the current directory.",
    "What is the current working directory?",
]

# Test configuration - models known to support tool calling
PROVIDER_LIST = [
    # OpenRouter free tier (cloud)
    "deepseek-free",
    # Ollama local models (require running ollama)
    "Qwen2.5-coder-14b",
    "qwen2.5-coder-7b-instruct-q8",
    "qwen2.5-coder-3b",
    "gemma4-4b-ollama",
]

# Providers to skip (not available or known issues)
SKIP_PROVIDERS = [
    "Poolside-laguna-free",  # Often unavailable
    "qwen2.5-coder-1.5b",    # Too small for reliable tool use
    "llama3.2",              # ⚠️ No tools in this model
    "llama3.1-8b",           # ⚠️ No tools in this model
    "deepseek-coder-6.7b",   # ⚠️ No tool support
    "Gemm4-26b-free",        # 🔴 Rate limited 
    "qwen3-next-80b",        # 🔴 Rate limited

]


def build_test_system_prompt():
    """Build a system prompt that includes tool definitions for testing."""
    return build_system_prompt()


def run_provider_test(provider_name: str, prompt: str, verbose: bool = False) -> dict:
    """Test a single provider with a prompt. Returns result dict."""
    pm = ProviderManager()
    provider = pm.get_provider(provider_name)
    
    result = {
        "provider": provider_name,
        "prompt": prompt,
        "success": False,
        "response_type": None,
        "has_tool_calls": False,
        "response_text": None,
        "error": None,
        "response_time_ms": None,
    }
    
    try:
        import time
        start = time.time()
        
        # Create a modified provider config with tools for this test
        test_provider_config = ProviderConfig(
            name=provider.name,
            provider_type=provider.provider_type,
            url=provider.url,
            model=provider.model,
            api_key_env_var=provider.api_key_env_var,
            attributes=provider.attributes,
            tools=TOOLS,  # Include tools for the test
        )
        
        # Build system prompt with tools
        system_prompt = build_test_system_prompt()
        
        conversation = [{"role": "user", "content": prompt}]
        response = call_llm(conversation, system_prompt, test_provider_config)
        elapsed_ms = int((time.time() - start) * 1000)
        
        result["response_time_ms"] = elapsed_ms
        result["response_text"] = response.text[:200] if response.text else None
        result["has_tool_calls"] = response.has_tool_calls
        
        # Check if response indicates an error
        if response.error:
            result["success"] = False
            result["error"] = response.error
            result["response_type"] = "error"
        else:
            result["success"] = True
            
            # Check for native tool_calls field (OpenAI style)
            if hasattr(response, 'tool_calls') and response.tool_calls:
                result["response_type"] = "tool_call"
                result["tool_names"] = [tc.name for tc in response.tool_calls]
            # Check for JSON tool call in text (Ollama style)
            elif response.text:
                try:
                    # Try to parse as JSON object with "name" field
                    data = json.loads(response.text.strip())
                    if isinstance(data, dict) and "name" in data:
                        result["response_type"] = "tool_call"
                        result["tool_names"] = [data["name"]]
                        result["has_tool_calls"] = True  # Update to reflect actual tool call
                    else:
                        result["response_type"] = "text"
                        result["tool_names"] = []
                except json.JSONDecodeError:
                    result["response_type"] = "text"
                    result["tool_names"] = []
            else:
                result["response_type"] = "text"
                result["tool_names"] = []
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def run_all_prompts_test(provider_name: str, verbose: bool = False) -> list:
    """Test a provider with all prompts."""
    if verbose:
        print(f"\nTesting {provider_name}...")
    
    results = []
    for prompt in TEST_PROMPTS:
        result = run_provider_test(provider_name, prompt, verbose=verbose)
        results.append(result)
        if verbose:
            # Print detailed result for this prompt
            resp_type = result.get('response_type', 'error')
            elapsed = result.get('response_time_ms', '?')
            print(f"  Prompt: {prompt[:50]}...")
            print(f"    -> {resp_type} ({elapsed}ms)")
            if result.get('tool_names'):
                print(f"    Tools called: {result['tool_names']}")
            if result.get('error'):
                print(f"    ERROR: {result['error']}")
    return results


def summarize_results(results: list) -> dict:
    """Summarize test results."""
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    with_tools = sum(1 for r in results if r.get("has_tool_calls"))
    errors = sum(1 for r in results if r.get("error"))
    
    return {
        "total": total,
        "successful": successful,
        "with_tool_calls": with_tools,
        "errors": errors,
        "success_rate": f"{successful}/{total}",
    }


def run_provider_tests(providers: list[str], verbose: bool = False, output_json: Optional[str] = None) -> dict:
    """Run tests for all specified providers."""
    all_results = {}
    
    for provider in providers:
        if provider in SKIP_PROVIDERS:
            if verbose:
                print(f"Skipping {provider} (known issues)")
            continue
            
        results = run_all_prompts_test(provider, verbose=verbose)
        summary = summarize_results(results)
        all_results[provider] = {
            "summary": summary,
            "detailed": results,
        }
    
    return all_results


def print_summary(all_results: dict):
    """Print a summary table of results."""
    print("\n" + "=" * 80)
    print(f"{'Provider':<30} {'Success':<12} {'Tool Calls':<15} {'Errors':<10}")
    print("-" * 80)
    
    for provider, data in sorted(all_results.items()):
        s = data["summary"]
        status = f"{s['successful']}/{s['total']}"
        tools = s["with_tool_calls"]
        errors = s["errors"]
        print(f"{provider:<30} {status:<12} {tools:<15} {errors:<10}")
    
    print("=" * 80)
    
    # Overall stats
    total_providers = len(all_results)
    providers_with_tools = sum(1 for p, d in all_results.items() if d["summary"]["with_tool_calls"] > 0)
    print(f"\nProviders with tool calls: {providers_with_tools}/{total_providers}")


def main():
    parser = argparse.ArgumentParser(description="Test LLM provider compatibility")
    parser.add_argument("--provider", "-p", help="Test specific provider (default: all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", "-j", help="Output results to JSON file")
    parser.add_argument("--list", "-l", action="store_true", help="List available providers")
    args = parser.parse_args()
    
    if args.list:
        print("Available providers:")
        for p in PROVIDER_LIST:
            status = "SKIP" if p in SKIP_PROVIDERS else "OK"
            print(f"  [{status}] {p}")
        print(f"\nTotal: {len(PROVIDER_LIST)} ({len(SKIP_PROVIDERS)} skipped)")
        return
    
    if args.provider:
        providers = [args.provider]
    else:
        providers = PROVIDER_LIST
    
    print(f"Testing {len(providers)} providers with {len(TEST_PROMPTS)} prompts each...")
    
    all_results = run_provider_tests(providers, args.verbose)
    
    print_summary(all_results)
    
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to {args.json}")
    
    # Return exit code based on results
    total_errors = sum(d["summary"]["errors"] for d in all_results.values())
    sys.exit(0 if total_errors == 0 else 1)


if __name__ == "__main__":
    main()