"""
Manual test script to validate GPT-5 API parameter behavior.

Run this script manually to verify GPT-5 parameter handling:
    python -m capstone.agent_v2.tests.manual.test_gpt5_params

Requirements:
- OPENAI_API_KEY environment variable set
- Latest litellm and openai packages installed
- Access to GPT-5 models
"""

import asyncio
import os
import sys
from typing import Dict, Any
import litellm


class GPT5ParameterValidator:
    """Validator for GPT-5 API parameter behavior."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            print("❌ OPENAI_API_KEY not set")
            sys.exit(1)
    
    async def test_traditional_temperature(self) -> Dict[str, Any]:
        """Test if temperature parameter is accepted for GPT-5."""
        print("\n🧪 Test 1: GPT-5 with temperature parameter")
        
        try:
            response = await litellm.acompletion(
                model="gpt-5",
                messages=[{"role": "user", "content": "Say 'hello' once."}],
                temperature=0.5,
                max_tokens=10
            )
            
            result = {
                "status": "accepted",
                "warning": "Temperature was accepted (unexpected for GPT-5)",
                "response": response.choices[0].message.content[:50]
            }
            print(f"   ⚠️  Temperature parameter ACCEPTED (unexpected)")
            print(f"   Response: {result['response']}")
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            result = {
                "status": "rejected",
                "error_type": error_type,
                "error_message": error_msg[:200]
            }
            
            if "temperature" in error_msg.lower() or "parameter" in error_msg.lower():
                print(f"   ✓ Temperature parameter REJECTED (expected)")
                print(f"   Error: {error_type}")
            else:
                print(f"   ❓ Unexpected error: {error_type}")
                print(f"   Message: {error_msg[:100]}")
        
        return result
    
    async def test_traditional_top_p(self) -> Dict[str, Any]:
        """Test if top_p parameter is accepted for GPT-5."""
        print("\n🧪 Test 2: GPT-5 with top_p parameter")
        
        try:
            response = await litellm.acompletion(
                model="gpt-5",
                messages=[{"role": "user", "content": "Say 'hello' once."}],
                top_p=0.9,
                max_tokens=10
            )
            
            result = {
                "status": "accepted",
                "warning": "top_p was accepted (unexpected for GPT-5)"
            }
            print(f"   ⚠️  top_p parameter ACCEPTED (unexpected)")
            
        except Exception as e:
            result = {
                "status": "rejected",
                "error_type": type(e).__name__,
                "error_message": str(e)[:200]
            }
            print(f"   ✓ top_p parameter REJECTED (expected)")
        
        return result
    
    async def test_gpt5_effort_parameter(self) -> Dict[str, Any]:
        """Test if effort parameter works for GPT-5."""
        print("\n🧪 Test 3: GPT-5 with effort parameter")
        
        results = {}
        for effort_level in ["low", "medium", "high"]:
            try:
                response = await litellm.acompletion(
                    model="gpt-5",
                    messages=[{"role": "user", "content": "Say 'hello' once."}],
                    effort=effort_level,
                    max_tokens=10
                )
                
                results[effort_level] = {
                    "status": "success",
                    "response": response.choices[0].message.content[:30]
                }
                print(f"   ✓ effort='{effort_level}' WORKS")
                
            except Exception as e:
                results[effort_level] = {
                    "status": "failed",
                    "error": str(e)[:100]
                }
                print(f"   ❌ effort='{effort_level}' FAILED: {type(e).__name__}")
        
        return results
    
    async def test_gpt5_reasoning_parameter(self) -> Dict[str, Any]:
        """Test if reasoning parameter works for GPT-5."""
        print("\n🧪 Test 4: GPT-5 with reasoning parameter")
        
        results = {}
        for reasoning_level in ["minimal", "balanced", "deep"]:
            try:
                response = await litellm.acompletion(
                    model="gpt-5",
                    messages=[{"role": "user", "content": "Say 'hello' once."}],
                    reasoning=reasoning_level,
                    max_tokens=10
                )
                
                results[reasoning_level] = {
                    "status": "success",
                    "response": response.choices[0].message.content[:30]
                }
                print(f"   ✓ reasoning='{reasoning_level}' WORKS")
                
            except Exception as e:
                results[reasoning_level] = {
                    "status": "failed",
                    "error": str(e)[:100]
                }
                print(f"   ❌ reasoning='{reasoning_level}' FAILED: {type(e).__name__}")
        
        return results
    
    async def test_combined_gpt5_params(self) -> Dict[str, Any]:
        """Test GPT-5 with combined effort + reasoning parameters."""
        print("\n🧪 Test 5: GPT-5 with effort + reasoning combined")
        
        try:
            response = await litellm.acompletion(
                model="gpt-5",
                messages=[{"role": "user", "content": "Explain quantum entanglement in one sentence."}],
                effort="medium",
                reasoning="balanced",
                max_tokens=50
            )
            
            result = {
                "status": "success",
                "response": response.choices[0].message.content
            }
            print(f"   ✓ Combined parameters WORK")
            print(f"   Response: {result['response'][:100]}")
            
        except Exception as e:
            result = {
                "status": "failed",
                "error_type": type(e).__name__,
                "error": str(e)[:200]
            }
            print(f"   ❌ Combined parameters FAILED: {type(e).__name__}")
        
        return result
    
    async def test_gpt4_still_works(self) -> Dict[str, Any]:
        """Verify GPT-4 models still work with traditional parameters."""
        print("\n🧪 Test 6: GPT-4.1 with traditional parameters (baseline)")
        
        try:
            response = await litellm.acompletion(
                model="gpt-4.1",
                messages=[{"role": "user", "content": "Say 'hello' once."}],
                temperature=0.7,
                max_tokens=10
            )
            
            result = {
                "status": "success",
                "response": response.choices[0].message.content
            }
            print(f"   ✓ GPT-4.1 with temperature WORKS (baseline confirmed)")
            
        except Exception as e:
            result = {
                "status": "failed",
                "error": str(e)[:200]
            }
            print(f"   ❌ GPT-4.1 FAILED (unexpected!): {type(e).__name__}")
        
        return result
    
    async def run_all_tests(self):
        """Run all validation tests."""
        print("=" * 60)
        print("GPT-5 Parameter Validation Suite")
        print("=" * 60)
        
        self.results["test_1_temperature"] = await self.test_traditional_temperature()
        self.results["test_2_top_p"] = await self.test_traditional_top_p()
        self.results["test_3_effort"] = await self.test_gpt5_effort_parameter()
        self.results["test_4_reasoning"] = await self.test_gpt5_reasoning_parameter()
        self.results["test_5_combined"] = await self.test_combined_gpt5_params()
        self.results["test_6_gpt4_baseline"] = await self.test_gpt4_still_works()
        
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        
        # Summarize findings
        print("\n📋 Findings:")
        print("1. Traditional parameters (temperature, top_p):")
        if self.results["test_1_temperature"]["status"] == "rejected":
            print("   ✓ Correctly rejected for GPT-5")
        else:
            print("   ⚠️  Unexpectedly accepted (may be silently ignored)")
        
        print("\n2. New GPT-5 parameters:")
        effort_results = self.results["test_3_effort"]
        if all(r["status"] == "success" for r in effort_results.values()):
            print("   ✓ 'effort' parameter fully supported")
        
        reasoning_results = self.results["test_4_reasoning"]
        if all(r["status"] == "success" for r in reasoning_results.values()):
            print("   ✓ 'reasoning' parameter fully supported")
        
        print("\n3. Backward compatibility:")
        if self.results["test_6_gpt4_baseline"]["status"] == "success":
            print("   ✓ GPT-4 with traditional parameters still works")
        
        return self.results


async def main():
    """Main entry point."""
    validator = GPT5ParameterValidator()
    results = await validator.run_all_tests()
    
    # Exit with appropriate code
    failures = sum(
        1 for test_name, result in results.items()
        if isinstance(result, dict) and result.get("status") == "failed"
    )
    
    print(f"\n{'✓' if failures == 0 else '❌'} Tests completed with {failures} failures")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())

