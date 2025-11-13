# Azure OpenAI Setup Guide

This guide explains how to configure the LLM Service to use Azure OpenAI instead of or alongside the standard OpenAI API.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step-by-Step Setup](#step-by-step-setup)
- [Environment Variables](#environment-variables)
- [Configuration Examples](#configuration-examples)
- [Hybrid Configuration](#hybrid-configuration)
- [API Version Compatibility](#api-version-compatibility)
- [Troubleshooting](#troubleshooting)
- [Common Error Messages](#common-error-messages)

---

## Overview

Azure OpenAI provides enterprise-grade hosting for OpenAI models with:

- **Data residency**: Keep data in specific Azure regions
- **Private networking**: VNet integration and private endpoints
- **Enterprise SLA**: Production-grade availability guarantees
- **Cost management**: Azure billing and cost controls
- **Compliance**: HIPAA, SOC 2, and other certifications

The LLM Service supports Azure OpenAI through deployment-based routing, where model aliases map to Azure deployment names.

---

## Prerequisites

Before starting, ensure you have:

1. **Azure Subscription**: Active subscription with Azure OpenAI access
2. **Azure OpenAI Resource**: Created in Azure Portal
3. **Model Deployments**: At least one model deployed (e.g., GPT-4)
4. **Access Credentials**: API key and endpoint URL from Azure Portal

### Request Azure OpenAI Access

Azure OpenAI requires application approval:

1. Visit [Azure OpenAI Access Request](https://aka.ms/oai/access)
2. Complete the application form
3. Wait for approval (typically 1-2 business days)
4. Once approved, create Azure OpenAI resource in Azure Portal

---

## Step-by-Step Setup

### Step 1: Create Azure OpenAI Resource

1. Sign in to [Azure Portal](https://portal.azure.com)
2. Search for "Azure OpenAI" in the search bar
3. Click **Create** → **Azure OpenAI**
4. Fill in the required fields:
   - **Subscription**: Your Azure subscription
   - **Resource group**: Create new or select existing
   - **Region**: Choose region (e.g., East US, West Europe)
   - **Name**: Unique name for your resource (e.g., `my-openai-resource`)
   - **Pricing tier**: Standard S0
5. Click **Review + Create** → **Create**
6. Wait for deployment to complete (~2-3 minutes)

### Step 2: Deploy Models

1. Navigate to your Azure OpenAI resource
2. Go to **Model deployments** (or click **Go to Azure OpenAI Studio**)
3. Click **Create new deployment**
4. Configure deployment:
   - **Model**: Select model (e.g., `gpt-4`, `gpt-35-turbo`)
   - **Model version**: Latest or specific version
   - **Deployment name**: Choose descriptive name (e.g., `gpt4-deployment`)
   - **Tokens per minute rate limit**: Set capacity (e.g., 10K)
5. Click **Create**
6. Repeat for each model you need

**Example deployments:**
- `gpt4-deployment` → GPT-4 (0613)
- `gpt4-mini-deployment` → GPT-4.1-mini
- `gpt35-turbo-deployment` → GPT-3.5 Turbo

### Step 3: Get Credentials

1. In Azure Portal, navigate to your Azure OpenAI resource
2. Go to **Keys and Endpoint** (under Resource Management)
3. Copy the following:
   - **KEY 1** (or KEY 2): Your API key
   - **Endpoint**: Full URL (e.g., `https://my-openai-resource.openai.azure.com/`)

### Step 4: Set Environment Variables

Set the following environment variables in your shell:

**PowerShell (Windows):**

```powershell
$env:AZURE_OPENAI_API_KEY = "your-api-key-from-step-3"
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
```

**Bash (Linux/Mac):**

```bash
export AZURE_OPENAI_API_KEY="your-api-key-from-step-3"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
```

**Verify environment variables are set:**

```powershell
# PowerShell
echo $env:AZURE_OPENAI_API_KEY
echo $env:AZURE_OPENAI_ENDPOINT
```

```bash
# Bash
echo $AZURE_OPENAI_API_KEY
echo $AZURE_OPENAI_ENDPOINT
```

### Step 5: Configure LLM Service

Edit `capstone/agent_v2/configs/llm_config.yaml`:

```yaml
providers:
  azure:
    enabled: true  # Enable Azure OpenAI
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"
    
    deployment_mapping:
      main: "gpt4-deployment"           # Your deployment name from Step 2
      fast: "gpt4-mini-deployment"      # Your deployment name from Step 2
      powerful: "gpt35-turbo-deployment"  # Your deployment name from Step 2
```

**Important:** Deployment names must exactly match what you created in Azure Portal (Step 2).

### Step 6: Test Connection

Run the agent or use the test connection method:

```python
from services.llm_service import LLMService

# Initialize service
llm_service = LLMService("configs/llm_config.yaml")

# Test Azure connection
import asyncio
result = asyncio.run(llm_service.test_azure_connection())

if result["success"]:
    print("✓ Azure OpenAI connected successfully")
    print(f"Available deployments: {result['deployments_available']}")
else:
    print("✗ Connection failed")
    print(f"Errors: {result['errors']}")
    print(f"Recommendations: {result['recommendations']}")
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `a1b2c3d4e5f6...` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://my-resource.openai.azure.com/` |

### Optional Variables

These can be customized in `llm_config.yaml` if you prefer different variable names:

```yaml
providers:
  azure:
    api_key_env: "MY_CUSTOM_AZURE_KEY"      # Default: AZURE_OPENAI_API_KEY
    endpoint_url_env: "MY_CUSTOM_ENDPOINT"  # Default: AZURE_OPENAI_ENDPOINT
```

---

## Configuration Examples

### Example 1: Simple Azure Setup

All models via Azure OpenAI:

```yaml
providers:
  azure:
    enabled: true
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"
    deployment_mapping:
      main: "gpt4-deployment"
      fast: "gpt35-turbo-deployment"
```

### Example 2: Multiple Models

Deploy various model versions:

```yaml
providers:
  azure:
    enabled: true
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"
    deployment_mapping:
      main: "gpt4-0613-deployment"
      fast: "gpt4-mini-deployment"
      powerful: "gpt5-preview-deployment"
      legacy: "gpt35-turbo-16k-deployment"
```

### Example 3: Development vs Production

Use environment-specific configs:

**llm_config_dev.yaml** (OpenAI for development):

```yaml
providers:
  openai:
    api_key_env: "OPENAI_API_KEY"
  azure:
    enabled: false
```

**llm_config_prod.yaml** (Azure for production):

```yaml
providers:
  azure:
    enabled: true
    api_key_env: "AZURE_OPENAI_API_KEY"
    endpoint_url_env: "AZURE_OPENAI_ENDPOINT"
    api_version: "2024-02-15-preview"
    deployment_mapping:
      main: "prod-gpt4-deployment"
      fast: "prod-gpt4-mini-deployment"
```

---

## Hybrid Configuration

### Understanding Azure Provider Mode

The Azure provider operates in **exclusive mode**: when `azure.enabled: true`, ALL LLM calls route through Azure OpenAI. You cannot mix Azure and OpenAI in a single config.

### Strategies for Hybrid Usage

#### Option 1: Multiple LLMService Instances

Create separate config files and service instances:

```python
# Initialize both providers
openai_service = LLMService("configs/llm_config_openai.yaml")
azure_service = LLMService("configs/llm_config_azure.yaml")

# Route calls based on requirements
standard_result = await openai_service.complete(messages, model="main")
enterprise_result = await azure_service.complete(messages, model="main")
```

#### Option 2: Environment-Based Switching

Use environment variables to select config:

```python
import os

config_file = os.getenv("LLM_CONFIG", "configs/llm_config.yaml")
llm_service = LLMService(config_file)
```

**PowerShell:**

```powershell
# Use Azure in production
$env:LLM_CONFIG = "configs/llm_config_prod_azure.yaml"

# Use OpenAI in development
$env:LLM_CONFIG = "configs/llm_config_dev_openai.yaml"
```

#### Option 3: Custom Router (Advanced)

Implement application-level routing:

```python
class HybridLLMRouter:
    def __init__(self):
        self.openai_service = LLMService("configs/llm_config_openai.yaml")
        self.azure_service = LLMService("configs/llm_config_azure.yaml")
    
    async def complete(self, messages, model=None, use_azure=False, **kwargs):
        """Route to Azure or OpenAI based on requirements."""
        if use_azure:
            return await self.azure_service.complete(messages, model, **kwargs)
        else:
            return await self.openai_service.complete(messages, model, **kwargs)

# Usage
router = HybridLLMRouter()

# Use OpenAI for development
dev_result = await router.complete(messages, model="fast", use_azure=False)

# Use Azure for production/enterprise
prod_result = await router.complete(messages, model="main", use_azure=True)
```

---

## API Version Compatibility

### Supported API Versions

Azure OpenAI uses versioned APIs. The API version controls available features and model support.

| API Version | Status | Features | Recommended For |
|-------------|--------|----------|-----------------|
| `2024-02-15-preview` | **Latest** | GPT-4, GPT-5, full feature set | New deployments |
| `2023-12-01-preview` | Stable | GPT-4, GPT-3.5 Turbo | Production |
| `2023-05-15` | Legacy | GPT-3.5 Turbo | Older deployments |

### How to Update API Version

1. Edit `llm_config.yaml`:

```yaml
providers:
  azure:
    api_version: "2024-02-15-preview"  # Change this value
```

2. Restart your application

3. Check logs for compatibility

### Version-Specific Considerations

**2024-02-15-preview:**
- Supports latest GPT-4 and GPT-5 models
- Includes new reasoning parameters (`effort`, `reasoning`)
- Best for new features

**2023-12-01-preview:**
- Stable for GPT-4 and GPT-3.5 Turbo
- Production-ready
- Good balance of features and stability

**2023-05-15:**
- Legacy version
- Limited to older models
- Use only if required for compatibility

### Checking Supported Versions

1. Visit [Azure OpenAI API Reference](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
2. Check your Azure Portal → OpenAI Resource → API Version dropdown
3. Review release notes for new versions

---

## Troubleshooting

### Quick Diagnostics Checklist

1. ✅ Azure OpenAI resource created and active
2. ✅ Models deployed with correct deployment names
3. ✅ API key copied from Azure Portal
4. ✅ Endpoint URL is HTTPS and includes resource name
5. ✅ Environment variables set in current shell
6. ✅ `azure.enabled: true` in config
7. ✅ Deployment mapping matches Azure Portal names exactly
8. ✅ API version is supported (check Azure docs)

### Testing Connection

Use the built-in connection test:

```python
import asyncio
from services.llm_service import LLMService

llm_service = LLMService("configs/llm_config.yaml")
result = asyncio.run(llm_service.test_azure_connection())

print("Success:", result["success"])
print("Errors:", result.get("errors", []))
print("Recommendations:", result.get("recommendations", []))
```

### Verification Steps

#### 1. Verify Environment Variables

**PowerShell:**

```powershell
echo $env:AZURE_OPENAI_API_KEY
echo $env:AZURE_OPENAI_ENDPOINT
```

**Expected output:**
- API key should be a long alphanumeric string
- Endpoint should be `https://your-resource.openai.azure.com/`

#### 2. Verify Azure Resource

1. Go to [Azure Portal](https://portal.azure.com)
2. Search for your resource name
3. Check **Status**: Should show "Succeeded" or "Running"
4. Go to **Model deployments**: Verify deployments exist

#### 3. Verify Configuration

Check `llm_config.yaml`:

```yaml
providers:
  azure:
    enabled: true  # Must be true
    deployment_mapping:
      main: "exact-deployment-name"  # Must match Azure Portal
```

#### 4. Check Application Logs

Look for these log messages:

**Successful initialization:**

```
azure_config_validated | endpoint_env=AZURE_OPENAI_API_KEY | api_version=2024-02-15-preview
azure_provider_initialized | provider=azure | enabled=true | deployment_count=2
provider_selected | provider=azure
```

**Configuration errors:**

```
azure_api_key_missing | env_var=AZURE_OPENAI_API_KEY
azure_endpoint_missing | env_var=AZURE_OPENAI_ENDPOINT
```

---

## Common Error Messages

### 1. "DeploymentNotFound" / "ResourceNotFound"

**Error:**

```
DeploymentNotFound: The deployment 'my-deployment' could not be found
```

**Cause:** Deployment name in config doesn't match Azure Portal

**Solution:**

1. Go to Azure Portal → OpenAI Resource → Model deployments
2. Copy exact deployment name (case-sensitive)
3. Update `llm_config.yaml`:

```yaml
deployment_mapping:
  main: "exact-name-from-portal"  # Must match exactly
```

---

### 2. "InvalidApiVersion" / "UnsupportedApiVersion"

**Error:**

```
InvalidApiVersion: The API version '2023-01-01' is not supported
```

**Cause:** API version is outdated or invalid

**Solution:**

1. Check [Azure OpenAI API versions](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
2. Update `llm_config.yaml`:

```yaml
providers:
  azure:
    api_version: "2024-02-15-preview"  # Use supported version
```

---

### 3. "AuthenticationError" / "InvalidApiKey"

**Error:**

```
AuthenticationError: Access denied due to invalid API key
```

**Cause:** API key is missing, incorrect, or expired

**Solution:**

1. Go to Azure Portal → OpenAI Resource → Keys and Endpoint
2. Copy KEY 1 or KEY 2
3. Set environment variable:

```powershell
$env:AZURE_OPENAI_API_KEY = "paste-key-here"
```

4. Restart application

---

### 4. "InvalidEndpoint" / "EndpointNotFound"

**Error:**

```
InvalidEndpoint: The endpoint 'https://wrong-name.openai.azure.com/' is not accessible
```

**Cause:** Endpoint URL is incorrect or resource doesn't exist

**Solution:**

1. Go to Azure Portal → OpenAI Resource → Keys and Endpoint
2. Copy endpoint URL (includes resource name)
3. Set environment variable:

```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://correct-resource.openai.azure.com/"
```

4. Verify format:
   - Must start with `https://`
   - Should contain `.openai.azure.com` or `.api.cognitive.microsoft.com`
   - Must end with `/`

---

### 5. "RateLimitError" / "TooManyRequests" / "429"

**Error:**

```
RateLimitError: Rate limit exceeded for deployment 'my-deployment'
```

**Cause:** Exceeded tokens-per-minute quota for deployment

**Solution:**

**Option 1: Wait and retry** (automatic with retry policy)

**Option 2: Increase capacity**
1. Go to Azure Portal → OpenAI Resource → Model deployments
2. Select deployment → Edit
3. Increase "Tokens per Minute Rate Limit"
4. Save changes

**Option 3: Adjust retry policy**

```yaml
retry_policy:
  max_attempts: 5          # More retries
  backoff_multiplier: 3    # Longer waits between retries
```

---

### 6. "No deployment mapping found"

**Error:**

```
ValueError: Azure provider is enabled but no deployment mapping found for model alias 'main'
```

**Cause:** Model alias not mapped to deployment name

**Solution:**

Add mapping for the model alias:

```yaml
providers:
  azure:
    deployment_mapping:
      main: "your-deployment-name"  # Add this mapping
      fast: "another-deployment"
```

---

### 7. Environment variables not set

**Error:**

```
azure_api_key_missing | env_var=AZURE_OPENAI_API_KEY
azure_endpoint_missing | env_var=AZURE_OPENAI_ENDPOINT
```

**Cause:** Environment variables not set in current shell

**Solution:**

Set variables and verify:

```powershell
# Set variables
$env:AZURE_OPENAI_API_KEY = "your-key"
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"

# Verify
echo $env:AZURE_OPENAI_API_KEY
echo $env:AZURE_OPENAI_ENDPOINT

# Restart application
```

---

### 8. "Azure provider is not enabled"

**Error:**

```
Azure provider is not enabled in configuration
```

**Cause:** `azure.enabled: false` in config

**Solution:**

Edit `llm_config.yaml`:

```yaml
providers:
  azure:
    enabled: true  # Change to true
```

---

## Additional Resources

- [Azure OpenAI Service Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure OpenAI API Reference](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
- [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [Request Azure OpenAI Access](https://aka.ms/oai/access)
- [LiteLLM Azure OpenAI Docs](https://docs.litellm.ai/docs/providers/azure)

---

## Support

If you encounter issues not covered in this guide:

1. Check application logs for detailed error messages
2. Use `test_azure_connection()` for diagnostics
3. Verify all setup steps completed
4. Review Azure Portal for resource status
5. Check Azure OpenAI service health status

For further assistance, consult Azure OpenAI documentation or support channels.

