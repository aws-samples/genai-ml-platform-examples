# Testing Examples for Deployed Endpoint

Quick reference for testing your deployed LLaMA fine-tuned model.

## 🚀 Quick Start

```bash
# 1. Find your endpoint name
aws sagemaker list-endpoints --name-contains llama

# 2. Run basic test
python test-endpoint.py --endpoint-name <your-endpoint-name>

# 3. Run all tests
python test-endpoint.py --endpoint-name <your-endpoint-name> --all-tests
```

---

## 📝 Test Prompts

### 1. Summarization

```python
prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
Summarize the following text in 2-3 sentences.

### Input:
Machine learning is a subset of artificial intelligence that focuses on the development of algorithms and statistical models that enable computers to improve their performance on a specific task through experience. Unlike traditional programming where explicit instructions are provided, machine learning systems learn patterns from data and make decisions with minimal human intervention.

### Response:
"""
```

### 2. Question Answering

```python
prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
Answer the following question based on the context provided.

### Input:
Context: The Amazon rainforest covers 5,500,000 square kilometers and is home to 10% of the world's species.

Question: How large is the Amazon rainforest?

### Response:
"""
```

### 3. Text Generation

```python
prompt = """Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Write a professional email to a customer apologizing for a delayed shipment.

### Response:
"""
```

### 4. Code Explanation

```python
prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
Explain what this code does in simple terms.

### Input:
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

### Response:
"""
```

---

## 🐍 Python Examples

### Basic Invocation

```python
import boto3
import json

runtime = boto3.client('sagemaker-runtime')

def invoke_model(endpoint_name, prompt):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 150,
            "temperature": 0.7,
            "top_p": 0.95,
            "do_sample": True
        }
    }
    
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps(payload)
    )
    
    result = json.loads(response['Body'].read().decode())
    return result[0]['generated_text']

# Use it
endpoint_name = "llama-finetuning-abc123-endpoint"
prompt = "Summarize: AI is transforming industries..."
response = invoke_model(endpoint_name, prompt)
print(response)
```

### Batch Processing

```python
import boto3
import json

runtime = boto3.client('sagemaker-runtime')

def process_batch(endpoint_name, prompts):
    results = []
    
    for i, prompt in enumerate(prompts):
        print(f"Processing {i+1}/{len(prompts)}...")
        
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 100}
        }
        
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(payload)
        )
        
        result = json.loads(response['Body'].read().decode())
        results.append(result[0]['generated_text'])
    
    return results

# Use it
prompts = [
    "Summarize: Machine learning...",
    "Explain: Quantum computing...",
    "Translate: Hello world..."
]

results = process_batch("your-endpoint-name", prompts)
for i, result in enumerate(results):
    print(f"\nResult {i+1}:")
    print(result)
```

### With Error Handling

```python
import boto3
import json
import time

runtime = boto3.client('sagemaker-runtime')

def invoke_with_retry(endpoint_name, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            payload = {
                "inputs": prompt,
                "parameters": {"max_new_tokens": 150}
            }
            
            response = runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Body=json.dumps(payload)
            )
            
            result = json.loads(response['Body'].read().decode())
            return result[0]['generated_text']
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
    
# Use it
try:
    response = invoke_with_retry("your-endpoint-name", "Your prompt")
    print(response)
except Exception as e:
    print(f"All retries failed: {e}")
```

---

## 🌐 REST API Examples

### Using AWS CLI

```bash
# Basic invocation
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name llama-finetuning-abc123-endpoint \
  --content-type application/json \
  --body '{"inputs":"Summarize: AI is...","parameters":{"max_new_tokens":100}}' \
  output.json

# View result
cat output.json | jq '.[0].generated_text'
```

### Using curl (with AWS Signature)

```bash
# Note: Requires AWS signature v4 - easier to use AWS CLI or SDK
# This is for reference only

# 1. Get temporary credentials
aws sts get-session-token

# 2. Use aws-curl or similar tool
aws-curl https://runtime.sagemaker.us-east-1.amazonaws.com/endpoints/your-endpoint/invocations \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"inputs":"Your prompt","parameters":{"max_new_tokens":100}}'
```

---

## 📊 Performance Testing

### Latency Test

```python
import boto3
import json
import time
import statistics

runtime = boto3.client('sagemaker-runtime')

def measure_latency(endpoint_name, prompt, num_requests=10):
    latencies = []
    
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 50}
    }
    
    for i in range(num_requests):
        start = time.time()
        
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(payload)
        )
        
        latency = time.time() - start
        latencies.append(latency)
        print(f"Request {i+1}: {latency:.2f}s")
    
    print(f"\nResults:")
    print(f"  Average: {statistics.mean(latencies):.2f}s")
    print(f"  Median: {statistics.median(latencies):.2f}s")
    print(f"  Min: {min(latencies):.2f}s")
    print(f"  Max: {max(latencies):.2f}s")

# Use it
measure_latency("your-endpoint-name", "Test prompt", num_requests=10)
```

### Throughput Test

```python
import boto3
import json
import time
from concurrent.futures import ThreadPoolExecutor

runtime = boto3.client('sagemaker-runtime')

def invoke_endpoint(endpoint_name, prompt):
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 50}
    }
    
    start = time.time()
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps(payload)
    )
    return time.time() - start

def measure_throughput(endpoint_name, num_concurrent=5, num_requests=20):
    prompts = [f"Test prompt {i}" for i in range(num_requests)]
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        latencies = list(executor.map(
            lambda p: invoke_endpoint(endpoint_name, p),
            prompts
        ))
    
    total_time = time.time() - start_time
    
    print(f"\nThroughput Test Results:")
    print(f"  Total requests: {num_requests}")
    print(f"  Concurrent requests: {num_concurrent}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Throughput: {num_requests/total_time:.2f} req/s")
    print(f"  Avg latency: {sum(latencies)/len(latencies):.2f}s")

# Use it
measure_throughput("your-endpoint-name", num_concurrent=5, num_requests=20)
```

---

## 🎯 Expected Response Format

### Successful Response:
```json
[
  {
    "generated_text": "Machine learning is a subset of AI that enables computers to learn from data and improve performance without explicit programming. It powers modern applications like recommendation systems and image recognition."
  }
]
```

### Error Response:
```json
{
  "error": "Model inference error",
  "message": "Invalid input format"
}
```

---

## 🔍 Debugging Tips

### Check Endpoint Status:
```python
import boto3

sm = boto3.client('sagemaker')
response = sm.describe_endpoint(EndpointName='your-endpoint-name')
print(f"Status: {response['EndpointStatus']}")
print(f"Instance Type: {response['ProductionVariants'][0]['InstanceType']}")
```

### View Recent Invocations:
```bash
# CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/SageMaker \
  --metric-name Invocations \
  --dimensions Name=EndpointName,Value=your-endpoint-name \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

### View Logs:
```bash
# Get log streams
aws logs describe-log-streams \
  --log-group-name /aws/sagemaker/Endpoints/your-endpoint-name \
  --order-by LastEventTime \
  --descending \
  --max-items 5

# Tail logs
aws logs tail /aws/sagemaker/Endpoints/your-endpoint-name --follow
```

---

## 💡 Tips

1. **Start with short prompts** to test connectivity
2. **Use temperature=0.7** for balanced creativity/consistency
3. **Adjust max_new_tokens** based on your use case (50-500)
4. **Monitor latency** - should be 2-5 seconds for typical prompts
5. **Check CloudWatch** if you see errors or slow responses

---

## 📞 Need Help?

- Check CloudWatch logs for errors
- Verify endpoint is "InService"
- Ensure IAM permissions are correct
- Review payload format matches examples above
