# Guide - Pulling Vespa metrics to Cloudwatch

This guide will take you through the steps necessary to set up an AWS Lambda pulling Vespa metrics to Cloudwatch.

## Prerequisites
You'll need to have the following available for this guide:
1. Vespa application endpoint
2. Application public certificate and private key
3. An AWS user with permissions to create these resourses:
    * SSM parameters
    * IAM roles and policies
    * Lambdas

## Store certificate and key in AWS Parameter Store
In the AWS console, go to AWS Systems manager -> Application Management -> Parameter Store.
Create two parameters, with application certificate and key as values respectively. Use the SecureString type, and encrypt using a KMS key of your choice.

Alternatively, if you use the AWS CLI, you can create the parameters using the following command:

```commandline
aws ssm put-parameter --name parameter_name --value "parameter value" --type SecureString --key-id "key id"
```
`--key-id` can be omitted, in which case the AWS-managed CMK will be used.

Note the ARNs of the newly created parameters. Its format will usually be `arn:aws:ssm:<region>:<account-number>:parameter/<parameter-name>`

## Create IAM policy and role
In the IAM service view, create a new policy, with the following permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "cloudwatch:PutMetricData",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameters",
                "ssm:GetParameter"
            ],
            "Resource": [
                "<Application key ARN>",
                "<Application certificate ARN>"
            ]
        }
    ]
}
```

Remember to insert the ARNs of your SSM parameters in the policy.

Next, create an IAM role. Choose AWS Lambda as the trusted entity and attach the previously created IAM permission policy.

## Create Lambda

In the Lambda service view, create a new function.
1. Choose **Author from scratch**
2. Use Python 3.x as runtime
3. Choose **Use an existing execution role**, and select the role you previously created.
4. Click create
5. Insert the contents of [vespa_cloudwatch_emitter.py](./vespa_cloudwatch_emitter.py) into the generated lambda function
6. Fill in the necessary environment variables:
    * **CERT_NAME**: Name of the previously created certificate parameter (note: name, not ARN)
    * **KEY_NAME**: Name of the previously created key parameter
    * **SSM_REGION**: The region in which you created the parameters, e.g. us-east-1
    * **VESPA_ENDPOINT**: The endpoint of your Vespa application
    * **CLOUDWATCH_NAMESPACE**: The Cloudwatch namespace where you want to store your metrics
7. Increase function timeout under **Basic settings** to 1 minute
7. Add trigger, with the following configuration:
    * Cloudwatch Events trigger
    * Create new rule
    * Use **Schedule expression** rule type
    * Set preferred schedule, e.g. `rate(5 minutes)`
9. Save Lambda

