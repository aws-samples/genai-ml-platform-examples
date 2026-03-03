# SageMaker Model Monitoring Workshop

This directory contains Jupyter notebooks for the SageMaker Unified Studio AIOps Workshop - Model Deployment and Monitoring module.

## Notebooks

### 01-endpoint-testing.ipynb
- Tests deployed SageMaker endpoints
- Generates sample inference requests
- Validates endpoint responses
- Creates data for monitoring analysis

### 02-model-monitoring.ipynb
- Sets up comprehensive model monitoring
- Configures data quality monitoring
- Implements model quality monitoring
- Creates monitoring schedules and alerts
- Integrates with CloudWatch dashboards

## Prerequisites

Before running these notebooks, ensure you have:

1. **Completed Lab 5.1**: Model deployment with data capture enabled
2. **SageMaker Unified Studio Domain**: Properly configured
3. **IAM Permissions**: Sufficient permissions for SageMaker Model Monitor
4. **Python Environment**: SageMaker Python SDK and required packages

## Workshop Flow

```
Lab 5.1: Model Deployment
    ↓
01-endpoint-testing.ipynb (Generate test data)
    ↓
02-model-monitoring.ipynb (Set up monitoring)
    ↓
Monitor via CloudWatch Dashboard
```

## Key Features

### Data Quality Monitoring
- **Baseline Creation**: Establish expected data characteristics
- **Drift Detection**: Identify changes in input data distribution
- **Automated Scheduling**: Hourly monitoring execution
- **Violation Alerts**: CloudWatch integration for notifications

### Model Quality Monitoring
- **Performance Tracking**: Monitor prediction accuracy over time
- **Ground Truth Integration**: Compare predictions with actual outcomes
- **Metric Analysis**: Track key performance indicators
- **Trend Analysis**: Identify model degradation patterns

### Infrastructure Integration
- **CloudWatch Dashboards**: Real-time monitoring visualization
- **SNS Notifications**: Automated alerting for violations
- **S3 Storage**: Monitoring reports and data capture
- **EventBridge Integration**: Event-driven automation

## Monitoring Architecture

```
SageMaker Endpoint (with Data Capture)
    ↓
S3 Data Capture Bucket
    ↓
Model Monitor Processing Jobs
    ↓
CloudWatch Metrics & Alarms
    ↓
SNS Notifications & EventBridge Events
```

## Files Structure

```
notebooks/
├── README.md                          # This file
├── 01-endpoint-testing.ipynb          # Endpoint testing and data generation
├── 02-model-monitoring.ipynb          # Model monitoring setup
├── images/                            # Architecture diagrams
│   ├── data-monitoring-architecture.png
│   ├── model-monitoring-architecture.png
│   ├── model-quality-monitor-execution.png
│   └── endpoint-details-data-capture.png
└── data/                              # Sample datasets
    └── sample_data.csv                # Sample training data
```

## Getting Started

1. **Start with Endpoint Testing**:
   ```bash
   jupyter notebook 01-endpoint-testing.ipynb
   ```

2. **Set Up Monitoring**:
   ```bash
   jupyter notebook 02-model-monitoring.ipynb
   ```

3. **Monitor Results**:
   - Check CloudWatch Dashboard
   - Review S3 monitoring reports
   - Verify SNS notifications

## Troubleshooting

### Common Issues

1. **No Endpoint Found**:
   - Ensure Lab 5.1 is completed
   - Verify endpoint is in "InService" status
   - Check data capture is enabled

2. **Monitoring Job Failures**:
   - Verify IAM permissions
   - Check S3 bucket access
   - Ensure sufficient data for analysis

3. **No Monitoring Reports**:
   - Wait for scheduled execution time
   - Check monitoring schedule status
   - Verify data capture has sufficient samples

### Required IAM Permissions

The execution role needs permissions for:
- SageMaker Model Monitor operations
- S3 read/write access to monitoring buckets
- CloudWatch metrics and alarms
- SNS topic publishing (if configured)

## Best Practices

1. **Data Volume**: Ensure sufficient inference data for meaningful analysis
2. **Baseline Quality**: Use representative training data for baselines
3. **Schedule Frequency**: Balance monitoring frequency with cost
4. **Alert Tuning**: Adjust thresholds to minimize false positives
5. **Regular Review**: Periodically review and update monitoring configuration

## Resources

- [SageMaker Model Monitor Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor.html)
- [CloudWatch Integration Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html)
- [Model Monitor API Reference](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateMonitoringSchedule.html)
- [Workshop Documentation](../../../content/modules/module5-deploy-ml-project/)

## Support

For workshop-specific questions:
1. Check the troubleshooting section above
2. Review CloudWatch logs for detailed error messages
3. Consult the workshop documentation
4. Contact workshop facilitators
